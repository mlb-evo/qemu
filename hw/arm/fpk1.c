/*
 * Experimental FPK1 Tegra30 diagnostic machine.
 *
 * This is NOT a production FPK1 boot chain.  An operator must explicitly
 * supply a raw boot fragment, its physical load address and its entry PC.
 * No MHI2 BCT, captured IRAM, Quickboot or peripheral wiring is assumed.
 */
#include "qemu/osdep.h"
#include "qemu/units.h"
#include "qemu/error-report.h"
#include "qemu/cutils.h"
#include "qemu/timer.h"
#include "chardev/char-fe.h"
#include "qapi/error.h"
#include "hw/core/boards.h"
#include "hw/arm/tegra30.h"
#include "hw/core/loader.h"
#include "hw/core/qdev-properties.h"
#include "hw/i2c/i2c.h"
#include "hw/misc/tegra30_slink.h"
#include "hw/sd/sd.h"
#include "system/blockdev.h"
#include "system/block-backend.h"
#include "system/address-spaces.h"
#include "system/reset.h"

/* Same record transport as mhi2_harman.c, so its guest shim and glhost work. */
#define GL_BULK_BYTES (1 * MiB)
#define GL_MAX_RECORD (16 * MiB + 20)
#define GL_TX_BYTES (2 * GL_MAX_RECORD)

typedef struct FPK1MachineState {
    MachineState parent_obj;
    Tegra30State *soc;
    char *load_address;
    char *entry_address;
    char *nor_image;
    MemoryRegion nor;
    uint64_t entry_pc;
    MemoryRegion gl_mmio;
    MemoryRegion gl_bulk;
    CharFrontend gl_chr;
    uint8_t gl_tx[4096];
    uint8_t *gl_bulk_tx, *gl_rx;
    unsigned gl_rx_count;
    bool gl_locked;
    QEMUTimer *gl_lock_timer;
    uint8_t gl_pending[GL_TX_BYTES];
    unsigned gl_tx_head, gl_tx_count;
    guint gl_watch;
} FPK1MachineState;

/* Optional experimental GLES transport, enabled by -chardev ...,id=glbridge.
 * This aperture is a host service, not a Tegra hardware device.
 */
static gboolean gl_writable(void *unused, GIOCondition condition, void *opaque);

static void gl_drain(FPK1MachineState *s)
{
    unsigned budget = 256 * KiB;

    while (s->gl_tx_count && budget && qemu_chr_fe_backend_open(&s->gl_chr)) {
        unsigned n = MIN(budget, MIN(s->gl_tx_count,
                                    GL_TX_BYTES - s->gl_tx_head));
        int written = qemu_chr_fe_write(&s->gl_chr,
                                       s->gl_pending + s->gl_tx_head, n);
        if (written <= 0) {
            break;
        }
        s->gl_tx_head = (s->gl_tx_head + written) % GL_TX_BYTES;
        s->gl_tx_count -= written;
        budget -= written;
    }
    if (s->gl_tx_count && !s->gl_watch &&
        qemu_chr_fe_backend_open(&s->gl_chr)) {
        s->gl_watch = qemu_chr_fe_add_watch(&s->gl_chr, G_IO_OUT | G_IO_HUP,
                                           gl_writable, s);
    }
}

static gboolean gl_writable(void *unused, GIOCondition condition, void *opaque)
{
    FPK1MachineState *s = opaque;
    s->gl_watch = 0;
    if (!(condition & G_IO_HUP)) {
        gl_drain(s);
    }
    return G_SOURCE_REMOVE;
}

static void gl_queue(FPK1MachineState *s, const uint8_t *data, unsigned length)
{
    if (length > GL_TX_BYTES - s->gl_tx_count) {
        error_report("glbridge: TX exceeds reserved record capacity");
        return;
    }
    unsigned tail = (s->gl_tx_head + s->gl_tx_count) % GL_TX_BYTES;
    unsigned first = MIN(length, GL_TX_BYTES - tail);
    memcpy(s->gl_pending + tail, data, first);
    memcpy(s->gl_pending, data + first, length - first);
    s->gl_tx_count += length;
    gl_drain(s);
}

static void gl_clear_tx(FPK1MachineState *s)
{
    if (s->gl_watch) {
        g_source_remove(s->gl_watch);
        s->gl_watch = 0;
    }
    s->gl_tx_head = s->gl_tx_count = 0;
}

static void gl_event(void *opaque, QEMUChrEvent event)
{
    FPK1MachineState *s = opaque;
    if (event == CHR_EVENT_OPENED) {
        gl_drain(s);
    } else if (event == CHR_EVENT_CLOSED) {
        gl_clear_tx(s);
        s->gl_rx_count = 0;
        s->gl_locked = false;
    }
}

static int gl_can_receive(void *opaque)
{
    FPK1MachineState *s = opaque;
    return GL_BULK_BYTES - s->gl_rx_count;
}
static void gl_receive(void *opaque, const uint8_t *buf, int size)
{
    FPK1MachineState *s = opaque;
    memcpy(s->gl_rx + s->gl_rx_count, buf, size);
    s->gl_rx_count += size;
}
/*
 * A client killed while holding the record lock would block every other
 * client. Release it after 2 s of guest time without bridge accesses and
 * drop any reply bytes the dead client left unread.
 */
#define GL_LOCK_IDLE_NS (2 * NANOSECONDS_PER_SECOND)

static void gl_lock_touch(FPK1MachineState *s)
{
    if (s->gl_locked) {
        timer_mod(s->gl_lock_timer,
                  qemu_clock_get_ns(QEMU_CLOCK_VIRTUAL) + GL_LOCK_IDLE_NS);
    }
}

static void gl_lock_expired(void *opaque)
{
    FPK1MachineState *s = opaque;

    if (s->gl_locked) {
        warn_report("glbridge: releasing record lock idle for 2 s");
        s->gl_locked = false;
        s->gl_rx_count = 0;
        qemu_chr_fe_accept_input(&s->gl_chr);
    }
}

static uint64_t gl_read(void *opaque, hwaddr addr, unsigned size)
{
    FPK1MachineState *s = opaque;
    /* Waiters polling the lock (addr 16) must not extend the holder's lease. */
    if (addr != 16) {
        gl_lock_touch(s);
    }
    if (addr == 0) {
        return 0x474c4252;
    }
    if (addr == 16) {
        /* Apply backpressure before accepting a record, without sleeping
         * under the BQL. The existing guest lock retry yields its CPU. */
        bool held = s->gl_locked || s->gl_tx_count > GL_TX_BYTES - GL_MAX_RECORD;
        if (!held) {
            s->gl_locked = true;
            gl_lock_touch(s);
        }
        return held;
    }
    if (addr == 8) {
        return MIN(s->gl_rx_count, 4096);
    }
    if (addr == 24) {
        return GL_BULK_BYTES;
    }
    if (addr == 32) {
        return s->gl_rx_count;
    }
    if (addr >= 0x2000 && addr - 0x2000 + size <= s->gl_rx_count) {
        uint64_t value = 0;
        for (unsigned i = 0; i < size; i++) {
            value |= (uint64_t)s->gl_rx[addr - 0x2000 + i] << (8 * i);
        }
        return value;
    }
    if (addr == 12 && s->gl_rx_count) {
        uint8_t value = s->gl_rx[0];
        memmove(s->gl_rx, s->gl_rx + 1, --s->gl_rx_count);
        qemu_chr_fe_accept_input(&s->gl_chr);
        return value;
    }
    return 0;
}
static void gl_write(void *opaque, hwaddr addr, uint64_t value, unsigned size)
{
    FPK1MachineState *s = opaque;
    gl_lock_touch(s);
    if (addr == 16) {
        s->gl_locked = false;
        timer_del(s->gl_lock_timer);
    } else if (((addr == 20 && value <= 4096) || addr == 36) &&
               value <= s->gl_rx_count) {
        s->gl_rx_count -= value;
        memmove(s->gl_rx, s->gl_rx + value, s->gl_rx_count);
        qemu_chr_fe_accept_input(&s->gl_chr);
    } else if (addr >= 0x1000 && addr + size <= 0x2000) {
        for (unsigned i = 0; i < size; i++) {
            s->gl_tx[addr - 0x1000 + i] = value >> (i * 8);
        }
    } else if (addr == 4 && value <= sizeof(s->gl_tx)) {
        gl_queue(s, s->gl_tx, value);
    } else if (addr == 28 && value <= GL_BULK_BYTES) {
        gl_queue(s, s->gl_bulk_tx, value);
    }
}
static const MemoryRegionOps gl_ops = {
    .read = gl_read, .write = gl_write, .endianness = DEVICE_LITTLE_ENDIAN,
    .valid = { .min_access_size = 1, .max_access_size = 4 },
};


static char *fpk1_get_load(Object *obj, Error **errp)
{
    return g_strdup(((FPK1MachineState *)obj)->load_address);
}

static void fpk1_set_load(Object *obj, const char *value, Error **errp)
{
    FPK1MachineState *s = (FPK1MachineState *)obj;
    g_free(s->load_address);
    s->load_address = g_strdup(value);
}

static char *fpk1_get_entry(Object *obj, Error **errp)
{
    return g_strdup(((FPK1MachineState *)obj)->entry_address);
}

static void fpk1_set_entry(Object *obj, const char *value, Error **errp)
{
    FPK1MachineState *s = (FPK1MachineState *)obj;
    g_free(s->entry_address);
    s->entry_address = g_strdup(value);
}

/* Explicit diagnostic NOR backing; no flash command/erase emulation. */
static char *fpk1_get_nor_image(Object *obj, Error **errp)
{
    return g_strdup(((FPK1MachineState *)obj)->nor_image);
}

static void fpk1_set_nor_image(Object *obj, const char *value, Error **errp)
{
    FPK1MachineState *s = (FPK1MachineState *)obj;
    g_free(s->nor_image);
    s->nor_image = g_strdup(value);
}

static void fpk1_reset(void *opaque)
{
    FPK1MachineState *s = opaque;
    for (int i = 0; i < TEGRA30_NUM_CPUS; i++) {
        cpu_reset(CPU(&s->soc->cpus[i]));
    }
    cpu_reset(CPU(&s->soc->lp_cpu));
    cpu_reset(CPU(&s->soc->avp));
    cpu_set_pc(CPU(&s->soc->avp), s->entry_pc);
}

static uint64_t parse_address(const char *value, const char *name)
{
    uint64_t address;

    if (!value || !*value || qemu_strtou64(value, NULL, 0, &address) < 0 ||
        address > UINT32_MAX) {
        error_report("fpk1: set a valid 32-bit -machine %s=0x... address", name);
        exit(1);
    }
    return address;
}

static void fpk1_init(MachineState *machine)
{
    FPK1MachineState *ms = (FPK1MachineState *)machine;
    uint64_t load = parse_address(ms->load_address, "load");
    ms->entry_pc = parse_address(ms->entry_address, "entry");

    if (!machine->firmware) {
        error_report("fpk1: diagnostic boot requires -bios <raw image>");
        exit(1);
    }

    Tegra30State *soc = TEGRA30(object_new(TYPE_TEGRA30));
    ms->soc = soc;
    object_property_add_child(OBJECT(machine), "soc", OBJECT(soc));

    memory_region_init_ram(&soc->emem, OBJECT(soc), "fpk1-dram",
                           machine->ram_size, &error_fatal);
    memory_region_add_subregion(get_system_memory(), 0x80000000, &soc->emem);
    memory_region_init_ram(&soc->iram, OBJECT(soc), "fpk1-iram",
                           0x40000, &error_fatal);
    memory_region_add_subregion(get_system_memory(), 0x40000000, &soc->iram);

    sysbus_realize_and_unref(SYS_BUS_DEVICE(soc), &error_fatal);

    if (ms->nor_image) {
        /* Verified library parameters: 64 MiB of NOR at 0x48000000. */
        int64_t nor_size = get_image_size(ms->nor_image, NULL);
        if (nor_size <= 0 || nor_size > 64 * MiB) {
            error_report("fpk1: nor-image must contain 1..64 MiB of raw NOR");
            exit(1);
        }
        memory_region_init_ram(&ms->nor, OBJECT(soc), "fpk1-nor",
                               64 * MiB, &error_fatal);
        memset(memory_region_get_ram_ptr(&ms->nor), 0xff, 64 * MiB);
        memory_region_add_subregion(get_system_memory(), 0x48000000, &ms->nor);
        if (load_image_targphys(ms->nor_image, 0x48000000, 64 * MiB,
                               &error_fatal) < 0) {
            error_report("fpk1: failed to load diagnostic NOR image");
            exit(1);
        }
        memory_region_set_readonly(&ms->nor, true);
    }

    Chardev *glchr = qemu_chr_find("glbridge");
    if (glchr) {
        /* Optional host GLES bridge (-chardev ...,id=glbridge), as on mhi2. */
        memory_region_init_ram(&ms->gl_bulk, OBJECT(soc),
                               "experimental-glbridge-bulk", 2 * GL_BULK_BYTES,
                               &error_fatal);
        memory_region_add_subregion(get_system_memory(), 0x5e000000,
                                    &ms->gl_bulk);
        ms->gl_bulk_tx = memory_region_get_ram_ptr(&ms->gl_bulk);
        ms->gl_rx = ms->gl_bulk_tx + GL_BULK_BYTES;
        qemu_chr_fe_init(&ms->gl_chr, glchr, &error_fatal);
        ms->gl_lock_timer = timer_new_ns(QEMU_CLOCK_VIRTUAL, gl_lock_expired, ms);
        qemu_chr_fe_set_handlers(&ms->gl_chr, gl_can_receive, gl_receive,
                                 gl_event, NULL, ms, NULL, true);
        memory_region_init_io(&ms->gl_mmio, OBJECT(machine), &gl_ops, ms,
                              "experimental-glbridge", 0x3000);
        memory_region_add_subregion(get_system_memory(), 0x5f000000,
                                    &ms->gl_mmio);
    }

    /*
     * Optional diagnostic eMMC on SDMMC4 (QNX "mnand", ioport 0x78000600),
     * e.g. -drive if=sd,index=0,format=raw,file=emmc.img. Absent by default.
     */
    DriveInfo *emmc_di = drive_get(IF_SD, 0, 0);
    if (emmc_di) {
        DeviceState *emmc = qdev_new(TYPE_EMMC);
        qdev_prop_set_drive(emmc, "drive", blk_by_legacy_dinfo(emmc_di));
        qdev_realize_and_unref(emmc, qdev_get_child_bus(soc->sdmmc[3], "sd-bus"),
                               &error_fatal);
    }

    /*
     * SLINK1 (SBC1) as SPI slave for gss_ipc's link to KSS, the cluster
     * microcontroller (libnvspislave, interrupt 91).  The master is an
     * external process on -chardev ...,id=kss; CC6 (hsk_to_kss, Tegra output)
     * and DD7 (hsk_to_gssn, KSS output) are the handshake lines.  Without the
     * chardev the slave never completes a transfer, as before.
     */
    DeviceState *slink = qdev_new(TYPE_TEGRA30_SLINK);
    Chardev *kss = qemu_chr_find("kss");
    if (kss) {
        qdev_prop_set_chr(slink, "chardev", kss);
    }
    sysbus_realize_and_unref(SYS_BUS_DEVICE(slink), &error_fatal);
    sysbus_mmio_map(SYS_BUS_DEVICE(slink), 0, 0x7000d400);
    sysbus_connect_irq(SYS_BUS_DEVICE(slink), 0,
                       qdev_get_gpio_in(DEVICE(&soc->a9mpcore), 59));
    qdev_connect_gpio_out(DEVICE(&soc->gpio), TEGRA30_GPIO_NR(28, 6),
                          qdev_get_gpio_in_named(slink, "hsk-in", 0));
    qdev_connect_gpio_out_named(slink, "hsk-out", 0,
                                qdev_get_gpio_in(DEVICE(&soc->gpio),
                                                 TEGRA30_GPIO_NR(29, 7)));

    /*
     * devg-nvtmon (Stage3) reads an NCT1008-compatible local/remote diode
     * sensor at 0x4c through /dev/i2c5, the DVC controller; its
     * /dev/nvtmon/current* nodes feed gtf2's temperature monitor.
     */
    I2CSlave *tmon = i2c_slave_new("tegra30-i2c-dbg", 0x4c);
    qdev_prop_set_bit(DEVICE(tmon), "temperature-sensor", true);
    i2c_slave_realize_and_unref(tmon, soc->i2c[4].bus, &error_fatal);

    /*
     * audio_player configures a TLV320DAC3100 at 0x18 on I2C1 (/dev/i2c1)
     * and requests a reboot when its soft reset is not acknowledged.
     */
    i2c_slave_create_simple(soc->i2c[0].bus, "tlv320dac3100", 0x18);

    /*
     * mostcoreapp talks to the MOST INIC at 0x20 on the same bus; the INIC
     * signals pending port messages on most_most_int (GPIO Y5, active low)
     * and is reset through most_rst_in (GPIO Z1).
     */
    I2CSlave *inic = i2c_slave_create_simple(soc->i2c[0].bus, "fpk1-inic",
                                             0x20);
    qdev_connect_gpio_out_named(DEVICE(inic), "int", 0,
                                qdev_get_gpio_in(DEVICE(&soc->gpio),
                                                 TEGRA30_GPIO_NR(24, 5)));
    qdev_connect_gpio_out(DEVICE(&soc->gpio), TEGRA30_GPIO_NR(25, 1),
                          qdev_get_gpio_in_named(DEVICE(inic), "reset", 0));

    /*
     * For this initial diagnostic harness, only loading into DRAM is allowed.
     * Require the entry PC to be inside the loaded image; a real FPK1 boot
     * handoff may need IRAM, NOR, a different load address and additional
     * hardware before this can execute meaningful firmware.
     */
    g_autofree gchar *bytes = NULL;
    gsize length = 0;
    if (!g_file_get_contents(machine->firmware, &bytes, &length, NULL) ||
        length == 0) {
        error_report("fpk1: unable to read nonempty raw boot image");
        exit(1);
    }
    const uint64_t end = 0x80000000ULL + machine->ram_size;
    if (load < 0x80000000ULL || load >= end || length > end - load ||
        ms->entry_pc < load || ms->entry_pc >= load + length ||
        (ms->entry_pc & 3)) {
        error_report("fpk1: load/entry must be aligned within loaded DRAM image "
                     "(load=0x%" PRIx64 ", entry=0x%" PRIx64 ", length=%zu)",
                     load, ms->entry_pc, (size_t)length);
        exit(1);
    }

    if (load_image_targphys(machine->firmware, load, end - load,
                            &error_fatal) < 0) {
        error_report("fpk1: failed to load image into DRAM");
        exit(1);
    }
    info_report("fpk1 diagnostic only: load=0x%" PRIx64
                " entry=0x%" PRIx64 " image=%zu bytes; "
                "no BootROM/BCT or vehicle peripherals", load,
                ms->entry_pc, (size_t)length);
    qemu_register_reset(fpk1_reset, ms);
}

static void fpk1_machine_init(MachineClass *mc)
{
    static const char * const cpu_types[] = {
        ARM_CPU_TYPE_NAME("cortex-a9"), NULL
    };
    object_class_property_add_str(OBJECT_CLASS(mc), "load",
                                  fpk1_get_load, fpk1_set_load);
    object_class_property_add_str(OBJECT_CLASS(mc), "entry",
                                  fpk1_get_entry, fpk1_set_entry);
    object_class_property_add_str(OBJECT_CLASS(mc), "nor-image",
                                  fpk1_get_nor_image, fpk1_set_nor_image);
    object_class_property_set_description(OBJECT_CLASS(mc), "nor-image",
        "Optional raw read-only NOR image at 0x48000000 (diagnostic only)");
    mc->desc = "FPK1 experimental Tegra30 diagnostic boot (not full board)";
    mc->init = fpk1_init;
    mc->min_cpus = TEGRA30_NUM_PROCS;
    mc->max_cpus = TEGRA30_NUM_PROCS;
    mc->default_cpus = TEGRA30_NUM_PROCS;
    mc->default_cpu_type = ARM_CPU_TYPE_NAME("cortex-a9");
    mc->valid_cpu_types = cpu_types;
    mc->default_ram_size = 512 * MiB;
    mc->default_ram_id = "fpk1.ram";
}

DEFINE_MACHINE_EXTENDED("fpk1", MACHINE, FPK1MachineState,
                        fpk1_machine_init, false, false, NULL)
