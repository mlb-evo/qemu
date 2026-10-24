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
#include "qapi/error.h"
#include "hw/core/boards.h"
#include "hw/arm/tegra30.h"
#include "hw/core/loader.h"
#include "system/address-spaces.h"
#include "system/reset.h"

typedef struct FPK1MachineState {
    MachineState parent_obj;
    Tegra30State *soc;
    char *load_address;
    char *entry_address;
    uint64_t entry_pc;
} FPK1MachineState;

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
