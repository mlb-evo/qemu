/*
 * nVidia Tegra30 SLINK (SPI) controller, slave mode only (research model).
 *
 * FPK1's gss_ipc talks to the cluster's KSS microcontroller through
 * libnvspislave: the Tegra is the SPI slave on SLINK1, KSS the master.  Only
 * what that library uses is modelled (packed PIO, RX-complete interrupt, the
 * TX/RX flush and error bits); timing, DMA and master mode are not.
 *
 * The master is an external process on the "chardev" property.  Messages:
 *
 *   master -> QEMU  'D' level        drive the master handshake line
 *                   'X' n data[n]    clock n bytes (master-out data)
 *   QEMU -> master  'C' level        the slave handshake line changed
 *                   'R' n data[n]    slave-out data of the matching 'X'
 *
 * An 'X' completes once software has armed a transfer (DMA_CTL bit 31); the
 * master is expected to wait for the slave handshake first, as KSS does.
 * 'D' 0 while an 'X' still waits for the slave drops that 'X' (an abort).
 * The handshake lines are qdev GPIOs wired to GPIO pins by the board.
 */

#include "qemu/osdep.h"
#include "hw/core/sysbus.h"
#include "hw/core/irq.h"
#include "hw/core/qdev-properties.h"
#include "hw/core/qdev-properties-system.h"
#include "qemu/log.h"
#include "qemu/module.h"
#include "hw/misc/tegra30_slink.h"

enum {
    REG_COMMAND  = 0x000,
    REG_COMMAND2 = 0x004,
    REG_STATUS   = 0x008,
    REG_MAS_DATA = 0x010,
    REG_SLV_DATA = 0x014,
    REG_DMA_CTL  = 0x018,
    REG_STATUS2  = 0x01c,
    REG_TX_FIFO  = 0x100,
    REG_RX_FIFO  = 0x180,
};

#define STATUS_RX_EMPTY  (1u << 23)
#define STATUS_TX_EMPTY  (1u << 21)
#define STATUS_TX_FLUSH  (1u << 26)
#define STATUS_RX_FLUSH  (1u << 27)
#define STATUS_RDY       (1u << 30)
#define STATUS_W1C       0x230d0000u   /* ERR, RX_OVF, TX_UNF, TX_OVF, RX_UNF, MODF */
#define DMA_CTL_GO       (1u << 31)
#define DMA_CTL_IE_RXC   (1u << 27)
#define DMA_CTL_IE_TXC   (1u << 26)
#define FIFO_WORDS       32

static void slink_update_irq(Tegra30SlinkState *s)
{
    qemu_set_irq(s->irq, (s->status & STATUS_RDY) &&
                         (s->dma_ctl & (DMA_CTL_IE_RXC | DMA_CTL_IE_TXC)));
}

/* Bytes in the armed transfer: DMA block count times the word length. */
static unsigned slink_xfer_bytes(Tegra30SlinkState *s)
{
    unsigned bits = (s->command & 0x1f) + 1;
    return ((s->dma_ctl & 0xffff) + 1) * bits / 8;
}

static void slink_send(Tegra30SlinkState *s, const uint8_t *buf, int len)
{
    if (qemu_chr_fe_backend_connected(&s->chr)) {
        qemu_chr_fe_write_all(&s->chr, buf, len);
    }
}

/* Exchange a pending master transfer with the armed slave transfer. */
static void slink_try_exchange(Tegra30SlinkState *s)
{
    uint8_t reply[2 + 255];
    unsigned n = s->xfer_len;

    if (!s->xfer_pending || !s->armed) {
        return;
    }
    if (n != slink_xfer_bytes(s)) {
        qemu_log_mask(LOG_GUEST_ERROR, "tegra30-slink: master clocked %u bytes, "
                      "slave armed for %u\n", n, slink_xfer_bytes(s));
    }
    reply[0] = 'R';
    reply[1] = n;
    for (unsigned i = 0; i < n; i++) {
        reply[2 + i] = i < s->tx_len ? s->tx[i] : 0xff;
        if (s->rx_len < sizeof(s->rx)) {
            s->rx[s->rx_len++] = s->xfer[i];
        }
    }
    /* Unsent TX bytes stay queued; software flushes them before re-arming. */
    unsigned used = MIN(n, s->tx_len);
    s->tx_len -= used;
    memmove(s->tx, s->tx + used, s->tx_len);
    s->xfer_pending = false;
    s->armed = false;
    s->dma_ctl &= ~DMA_CTL_GO;
    s->status |= STATUS_RDY;
    slink_send(s, reply, 2 + n);
    slink_update_irq(s);
}

static uint64_t slink_read(void *opaque, hwaddr offset, unsigned size)
{
    Tegra30SlinkState *s = TEGRA30_SLINK(opaque);
    unsigned rx_words = DIV_ROUND_UP(s->rx_len - s->rx_pos, 4);
    unsigned tx_words = DIV_ROUND_UP(s->tx_len, 4);
    uint32_t value = 0;

    switch (offset) {
    case REG_COMMAND:
        return s->command;
    case REG_COMMAND2:
        return s->command2;
    case REG_STATUS:
        return s->status | (rx_words ? 0 : STATUS_RX_EMPTY) |
               (tx_words ? 0 : STATUS_TX_EMPTY);
    case REG_DMA_CTL:
        return s->dma_ctl;
    case REG_STATUS2:
        return (rx_words << 16) | (FIFO_WORDS - MIN(tx_words, FIFO_WORDS));
    case REG_RX_FIFO:
        /* Packed 8-bit words: the first byte on the wire is the low byte. */
        for (int i = 0; i < 4 && s->rx_pos < s->rx_len; i++) {
            value |= (uint32_t)s->rx[s->rx_pos++] << (8 * i);
        }
        return value;
    case REG_MAS_DATA:
    case REG_SLV_DATA:
        return 0;
    default:
        qemu_log_mask(LOG_UNIMP, "tegra30-slink: read 0x%03x\n", (int)offset);
        return 0;
    }
}

static void slink_write(void *opaque, hwaddr offset, uint64_t value,
                        unsigned size)
{
    Tegra30SlinkState *s = TEGRA30_SLINK(opaque);

    switch (offset) {
    case REG_COMMAND:
        s->command = value;
        break;
    case REG_COMMAND2:
        s->command2 = value;
        break;
    case REG_STATUS:
        s->status &= ~(value & STATUS_W1C);
        if (value & STATUS_TX_FLUSH) {
            s->tx_len = 0;
        }
        if (value & STATUS_RX_FLUSH) {
            s->rx_len = s->rx_pos = 0;
            s->status &= ~STATUS_RDY;
        }
        if (value & STATUS_RDY) {
            s->status &= ~STATUS_RDY;
        }
        slink_update_irq(s);
        break;
    case REG_DMA_CTL:
        s->dma_ctl = value;
        if (value & DMA_CTL_GO) {
            s->armed = true;
            s->status &= ~STATUS_RDY;
        } else {
            s->armed = false;
        }
        slink_update_irq(s);
        slink_try_exchange(s);
        break;
    case REG_TX_FIFO:
        for (int i = 0; i < 4 && s->tx_len < sizeof(s->tx); i++) {
            s->tx[s->tx_len++] = value >> (8 * i);
        }
        break;
    default:
        qemu_log_mask(LOG_UNIMP, "tegra30-slink: write 0x%03x = 0x%08x\n",
                      (int)offset, (unsigned)value);
        break;
    }
}

static const MemoryRegionOps slink_ops = {
    .read = slink_read,
    .write = slink_write,
    .endianness = DEVICE_NATIVE_ENDIAN,
    .valid = {
        .min_access_size = 4,
        .max_access_size = 4,
    },
};

/* Slave handshake line from the GPIO block, forwarded to the master. */
static void slink_hsk_in(void *opaque, int n, int level)
{
    Tegra30SlinkState *s = opaque;
    uint8_t msg[2] = { 'C', !!level };

    if (s->hsk_in != !!level) {
        s->hsk_in = !!level;
        slink_send(s, msg, sizeof(msg));
    }
}

static int slink_can_receive(void *opaque)
{
    Tegra30SlinkState *s = opaque;

    /*
     * Input keeps flowing while an exchange waits for the slave to arm, so
     * that the master can still drop its handshake line and abort it.
     */
    return sizeof(s->msg) - s->msg_len;
}

static void slink_receive(void *opaque, const uint8_t *buf, int size)
{
    Tegra30SlinkState *s = opaque;

    for (int i = 0; i < size; i++) {
        unsigned need;

        s->msg[s->msg_len++] = buf[i];
        switch (s->msg[0]) {
        case 'D':
            need = 2;
            break;
        case 'X':
            need = s->msg_len < 2 ? 2 : 2 + s->msg[1];
            break;
        default:
            qemu_log_mask(LOG_GUEST_ERROR, "tegra30-slink: bad message 0x%02x\n",
                          s->msg[0]);
            s->msg_len = 0;
            continue;
        }
        if (s->msg_len < need) {
            continue;
        }
        if (s->msg[0] == 'D') {
            if (!s->msg[1] && s->xfer_pending) {
                /* The master dropped its handshake: the cycle is aborted. */
                s->xfer_pending = false;
            }
            qemu_set_irq(s->hsk_out, s->msg[1]);
        } else {
            if (s->xfer_pending) {
                qemu_log_mask(LOG_GUEST_ERROR, "tegra30-slink: master clocked "
                              "again before the slave armed\n");
            }
            s->xfer_len = s->msg[1];
            memcpy(s->xfer, s->msg + 2, s->xfer_len);
            s->xfer_pending = true;
            slink_try_exchange(s);
        }
        s->msg_len = 0;
    }
}

static void slink_event(void *opaque, QEMUChrEvent event)
{
    Tegra30SlinkState *s = opaque;
    uint8_t msg[2] = { 'C', s->hsk_in };

    if (event == CHR_EVENT_OPENED) {
        s->msg_len = 0;
        slink_send(s, msg, sizeof(msg));
    } else if (event == CHR_EVENT_CLOSED) {
        s->msg_len = 0;
        s->xfer_pending = false;
        qemu_set_irq(s->hsk_out, 0);
    }
}

static void slink_reset(DeviceState *dev)
{
    Tegra30SlinkState *s = TEGRA30_SLINK(dev);

    s->command = s->command2 = s->status = s->dma_ctl = 0;
    s->armed = false;
    s->tx_len = s->rx_len = s->rx_pos = 0;
    slink_update_irq(s);
}

static void slink_realize(DeviceState *dev, Error **errp)
{
    Tegra30SlinkState *s = TEGRA30_SLINK(dev);

    qemu_chr_fe_set_handlers(&s->chr, slink_can_receive, slink_receive,
                             slink_event, NULL, s, NULL, true);
}

static void slink_init(Object *obj)
{
    Tegra30SlinkState *s = TEGRA30_SLINK(obj);

    memory_region_init_io(&s->iomem, obj, &slink_ops, s, TYPE_TEGRA30_SLINK,
                          0x200);
    sysbus_init_mmio(SYS_BUS_DEVICE(obj), &s->iomem);
    sysbus_init_irq(SYS_BUS_DEVICE(obj), &s->irq);
    qdev_init_gpio_in_named(DEVICE(obj), slink_hsk_in, "hsk-in", 1);
    qdev_init_gpio_out_named(DEVICE(obj), &s->hsk_out, "hsk-out", 1);
}

static const Property slink_properties[] = {
    DEFINE_PROP_CHR("chardev", Tegra30SlinkState, chr),
};

static void slink_class_init(ObjectClass *klass, const void *data)
{
    DeviceClass *dc = DEVICE_CLASS(klass);

    dc->realize = slink_realize;
    device_class_set_legacy_reset(dc, slink_reset);
    device_class_set_props(dc, slink_properties);
}

static const TypeInfo slink_info = {
    .name          = TYPE_TEGRA30_SLINK,
    .parent        = TYPE_SYS_BUS_DEVICE,
    .instance_init = slink_init,
    .instance_size = sizeof(Tegra30SlinkState),
    .class_init    = slink_class_init,
};

static void slink_register(void)
{
    type_register_static(&slink_info);
}

type_init(slink_register)
