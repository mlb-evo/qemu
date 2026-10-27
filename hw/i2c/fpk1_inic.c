/*
 * MOST INIC control port on FPK1 I2C1 0x20 (research stub).
 *
 * mostcoreapp runs MOST NetServices in "mixed i2c, usb" mode: control
 * messages travel over I2C as port messages, packet data over USB. A port
 * message is PML (16-bit big-endian length of the rest), PMHL (header
 * length), FPH (bits 4:3 FIFO, bits 2:1 type: 0 command, 1 status) and the
 * header payload. The host writes one message per I2C write transaction.
 * The INIC signals a pending message by pulling /dev/nvgpio/most_most_int
 * (GPIO Y5) low; the host then reads the 2-byte PML and re-reads the whole
 * message (PML included) in a second read transaction.
 *
 * The FIFO synchronisation handshake is answered: the sync command (status
 * byte 0xc0) gets a status message with code 0x10, which NetServices
 * reports to its sync observer as success (0x100).
 *
 * Every data message is acknowledged with a status message on its FIFO
 * (status byte 0x44: code 0x04, success); without it NetServices retries and
 * finally reports the transmission as failed. The host acknowledges ours the
 * same way.
 *
 * INIC control messages (ICM, FIFO 2) are data messages (PMHL 1, FPH 0x14)
 * whose body is FktID[11:4], FktID[3:0] << 4 | OPType, TelID << 4 |
 * len[11:8], len[7:0], data. Answered: 0x300 (attach state, one byte: the
 * host sets 1 to attach and 2 once its init is complete), 0x30a (watchdog
 * configuration, reported disabled); 0x309 (watchdog trigger) only needs the
 * acknowledgement; other SetGet requests echo their data as the status.
 * While attaching (state 1) the INIC pushes the statuses NetServices waits
 * for, see fpk1_inic_attach_statuses(). Every other message is logged.
 *
 * The host resets the INIC through /dev/nvgpio/most_rst_in (GPIO Z1); any
 * edge on the "reset" input drops pending messages. After a reset INT stays
 * low until the host's first read: the first arm of the Y5 interrupt leaves
 * it masked, and mostcoreapp's one-off level check at interface start only
 * picks up the first reply if INT is already low.
 */

#include "qemu/osdep.h"
#include "qemu/log.h"
#include "qemu/module.h"
#include "qemu/timer.h"
#include "hw/core/irq.h"
#include "hw/i2c/i2c.h"
#include "qom/object.h"

#define TYPE_FPK1_INIC "fpk1-inic"
OBJECT_DECLARE_SIMPLE_TYPE(Fpk1InicState, FPK1_INIC)

#define INIC_MSG_MAX 256

#define PMP_FPH_TYPE(fph)   (((fph) >> 1) & 3)
#define PMP_TYPE_CMD        0
#define PMP_TYPE_STATUS     1
#define PMP_TYPE_DATA       2
#define PMP_FPH_FIFO(fph)   (((fph) >> 3) & 3)
#define PMP_FIFO_ICM        2
#define PMP_CMD_SYNC        0xc0
#define PMP_STATUS_SYNCED   0x10
#define PMP_STATUS_ACK      0x44

#define ICM_FPH             0x14
#define MCM_FPH             0x04
#define OP_SET              0x0
#define OP_GET              0x1
#define OP_SETGET           0x2
#define OP_STATUS           0xc
#define FKT_VERSION         0x200
#define FKT_ATTACH          0x300
#define FKT_WATCHDOG_TRIG   0x309
#define FKT_WATCHDOG        0x30a
#define FBLOCK_NETBLOCK     0x01

struct Fpk1InicState {
    I2CSlave parent_obj;

    qemu_irq int_n;
    uint8_t attach;
    uint8_t rx[INIC_MSG_MAX];
    unsigned rx_len;
    GQueue tx;
    unsigned tx_pos;
    bool reading;
    /* INT held low after reset until the host's first read. */
    bool ready;
};

static bool fpk1_inic_debug(void)
{
    static int dbg = -1;

    if (dbg < 0) {
        dbg = getenv("FPK1_INIC_DEBUG") != NULL;
    }
    return dbg;
}

static void fpk1_inic_trace(const char *what, const uint8_t *data,
                            unsigned len)
{
    if (fpk1_inic_debug()) {
        g_autoptr(GString) hex = g_string_new(NULL);

        for (unsigned i = 0; i < len; i++) {
            g_string_append_printf(hex, " %02x", data[i]);
        }
        fprintf(stderr, "[fpk1-inic %" PRId64 "] %s%s\n",
                qemu_clock_get_ms(QEMU_CLOCK_VIRTUAL), what, hex->str);
    }
}

static void fpk1_inic_update_int(Fpk1InicState *s)
{
    qemu_set_irq(s->int_n, g_queue_is_empty(&s->tx) && !s->ready);
}

static void fpk1_inic_queue(Fpk1InicState *s, const uint8_t *data, size_t len)
{
    fpk1_inic_trace("tx", data, len);
    g_queue_push_tail(&s->tx, g_byte_array_append(g_byte_array_new(),
                                                  data, len));
    fpk1_inic_update_int(s);
}

static void fpk1_inic_log(const char *what, const uint8_t *data, unsigned len)
{
    g_autoptr(GString) hex = g_string_new(NULL);

    for (unsigned i = 0; i < len; i++) {
        g_string_append_printf(hex, " %02x", data[i]);
    }
    qemu_log_mask(LOG_UNIMP, "%s: %s%s\n", TYPE_FPK1_INIC, what, hex->str);
}

static void fpk1_inic_icm_status(Fpk1InicState *s, unsigned fkt,
                                 const uint8_t *data, unsigned len)
{
    uint8_t m[8 + 32] = {
        (6 + len) >> 8, 6 + len, 1, ICM_FPH,
        fkt >> 4, (fkt & 0xf) << 4 | OP_STATUS, len >> 8, len,
    };

    assert(len <= sizeof(m) - 8);
    memcpy(m + 8, data, len);
    fpk1_inic_queue(s, m, 8 + len);
}

/*
 * MOST control message (MCM, FIFO 0) status from an FBlock of the local
 * node; the INIC hosts NetBlock. MCM and ICM share the extended header:
 * flags A = 0x01 (B follows), B = 0x10 (FBlock and instance follow); the
 * source address defaults to 1, which routes it to the NetBlock table.
 */
static void fpk1_inic_mcm_status(Fpk1InicState *s, uint8_t fblock,
                                 unsigned fkt, const uint8_t *data,
                                 unsigned len)
{
    uint8_t m[12 + 32] = {
        (10 + len) >> 8, 10 + len, 5, MCM_FPH | 1, 0x01, 0x10, fblock, 0x00,
        fkt >> 4, (fkt & 0xf) << 4 | OP_STATUS, len >> 8, len,
    };

    assert(len <= sizeof(m) - 12);
    memcpy(m + 12, data, len);
    fpk1_inic_queue(s, m, 12 + len);
}

/*
 * The statuses NetServices collects while the attach is in progress (state
 * 1). The version record carries the mask of required ones (0x000993fb in
 * its first entry); when all have arrived it raises observer trigger 0x800,
 * the remaining services finish init and the host sets the attach state to 2.
 * Values describe a node whose MOST network is off.
 */
static void fpk1_inic_attach_statuses(Fpk1InicState *s)
{
    static const uint8_t version[20] = {
        0x00, 0x00, 0x08, 0x11, 0x10, 0x10, 0x03, 0x00, 0x00, 0x90, 0x00,
    };
    static const uint8_t node_address[2] = { 0xff, 0xff };
    static const uint8_t group_address[2] = { 0x03, 0x00 };
    static const uint8_t netblock_7[2] = { 0x00, 0x00 };
    static const uint8_t zero[5] = { 0 };
    /* NI state, node address (unknown), last byte. */
    static const uint8_t ni_info[4] = { 0x00, 0xff, 0xff, 0x00 };

    fpk1_inic_icm_status(s, FKT_VERSION, version, sizeof(version));
    fpk1_inic_mcm_status(s, FBLOCK_NETBLOCK, 0x003, node_address, 2);
    fpk1_inic_mcm_status(s, FBLOCK_NETBLOCK, 0x004, group_address, 2);
    fpk1_inic_mcm_status(s, FBLOCK_NETBLOCK, 0x007, netblock_7, 2);
    fpk1_inic_icm_status(s, 0x502, zero, 1);
    fpk1_inic_icm_status(s, 0x503, zero, 1); /* net interface off */
    fpk1_inic_icm_status(s, 0x506, zero, 1);
    fpk1_inic_icm_status(s, 0x50a, ni_info, sizeof(ni_info));
    fpk1_inic_icm_status(s, 0x50e, zero, 2);
    fpk1_inic_icm_status(s, 0x407, zero, 1);
    fpk1_inic_icm_status(s, 0x40e, zero, 5);
}

static void fpk1_inic_icm(Fpk1InicState *s, const uint8_t *b, unsigned blen)
{
    static const uint8_t version[20] = {
        0x00, 0x00, 0x08, 0x11, 0x10, 0x10, 0x03, 0x00, 0x00, 0x90, 0x00,
    };
    /* Mode, timeout 0xffff (disabled), reserved. */
    static const uint8_t watchdog[5] = { 0x00, 0xff, 0xff, 0x00, 0x00 };
    unsigned fkt, op, len;

    if (blen < 4) {
        fpk1_inic_log("short ICM", b, blen);
        return;
    }
    fkt = (b[0] << 4) | (b[1] >> 4);
    op = b[1] & 0xf;
    len = ((b[2] & 0xf) << 8) | b[3];
    if (len > blen - 4) {
        fpk1_inic_log("truncated ICM", b, blen);
        return;
    }
    if (fkt == FKT_ATTACH && (op == OP_SET || op == OP_SETGET || op == OP_GET)) {
        if (op != OP_GET && len >= 1) {
            s->attach = b[4];
        }
        fpk1_inic_icm_status(s, fkt, &s->attach, 1);
        if (op != OP_GET && s->attach == 1) {
            fpk1_inic_attach_statuses(s);
        }
        return;
    }
    if (fkt == FKT_VERSION && op == OP_GET) {
        fpk1_inic_icm_status(s, fkt, version, sizeof(version));
        return;
    }
    if (fkt == FKT_WATCHDOG && op == OP_GET) {
        fpk1_inic_icm_status(s, fkt, watchdog, sizeof(watchdog));
        return;
    }
    if (fkt == FKT_WATCHDOG_TRIG) {
        return;
    }
    if (op == OP_SETGET && len <= 32) {
        /* Plain properties (e.g. 0x30f) report the value just set. */
        fpk1_inic_icm_status(s, fkt, b + 4, len);
        return;
    }
    fpk1_inic_log("unhandled ICM", b, blen);
}

static void fpk1_inic_handle(Fpk1InicState *s)
{
    const uint8_t *m = s->rx;
    unsigned pml;

    fpk1_inic_trace("rx", m, s->rx_len);
    if (s->rx_len < 5) {
        fpk1_inic_log("short message", m, s->rx_len);
        return;
    }
    pml = (m[0] << 8) | m[1];
    if (pml + 2 != s->rx_len) {
        fpk1_inic_log("length mismatch", m, s->rx_len);
    }
    if (m[2] == 2 && PMP_FPH_TYPE(m[3]) == PMP_TYPE_CMD &&
        m[4] == PMP_CMD_SYNC) {
        const uint8_t synced[] = {
            0x00, 0x03, 0x02,
            (m[3] & ~6) | (PMP_TYPE_STATUS << 1),
            PMP_CMD_SYNC | PMP_STATUS_SYNCED,
        };
        fpk1_inic_queue(s, synced, sizeof(synced));
        return;
    }
    if (PMP_FPH_TYPE(m[3]) == PMP_TYPE_STATUS) {
        return; /* the host acknowledging one of our messages */
    }
    if (PMP_FPH_TYPE(m[3]) == PMP_TYPE_DATA) {
        const uint8_t ack[] = {
            0x00, 0x03, 0x02,
            PMP_FPH_FIFO(m[3]) << 3 | PMP_TYPE_STATUS << 1, PMP_STATUS_ACK,
        };
        fpk1_inic_queue(s, ack, sizeof(ack));
        if (m[2] == 1 && PMP_FPH_FIFO(m[3]) == PMP_FIFO_ICM) {
            fpk1_inic_icm(s, m + 4, s->rx_len - 4);
            return;
        }
    }
    fpk1_inic_log("unhandled", m, s->rx_len);
}

static int fpk1_inic_event(I2CSlave *i2c, enum i2c_event event)
{
    Fpk1InicState *s = FPK1_INIC(i2c);
    GByteArray *head;

    switch (event) {
    case I2C_START_SEND:
        s->rx_len = 0;
        s->reading = false;
        break;
    case I2C_START_RECV:
        s->tx_pos = 0;
        s->reading = true;
        break;
    case I2C_FINISH:
        if (!s->reading) {
            fpk1_inic_handle(s);
            break;
        }
        /* A read covering the whole message consumes it. */
        head = g_queue_peek_head(&s->tx);
        if (fpk1_inic_debug()) {
            uint8_t n = MIN(s->tx_pos, 255);
            fpk1_inic_trace("read", &n, 1);
        }
        if (head && s->tx_pos >= head->len) {
            g_byte_array_unref(g_queue_pop_head(&s->tx));
        }
        s->ready = false;
        fpk1_inic_update_int(s);
        break;
    default:
        break;
    }
    return 0;
}

static uint8_t fpk1_inic_recv(I2CSlave *i2c)
{
    Fpk1InicState *s = FPK1_INIC(i2c);
    GByteArray *head = g_queue_peek_head(&s->tx);
    unsigned pos = s->tx_pos++;

    return head && pos < head->len ? head->data[pos] : 0;
}

static int fpk1_inic_send(I2CSlave *i2c, uint8_t data)
{
    Fpk1InicState *s = FPK1_INIC(i2c);

    if (s->rx_len < sizeof(s->rx)) {
        s->rx[s->rx_len++] = data;
    }
    return 0;
}

static void fpk1_inic_reset(DeviceState *dev)
{
    Fpk1InicState *s = FPK1_INIC(dev);

    g_queue_clear_full(&s->tx, (GDestroyNotify)g_byte_array_unref);
    s->rx_len = 0;
    s->tx_pos = 0;
    s->reading = false;
    s->attach = 0;
    s->ready = true;
    fpk1_inic_update_int(s);
}

static void fpk1_inic_reset_in(void *opaque, int n, int level)
{
    fpk1_inic_trace(level ? "reset high" : "reset low", NULL, 0);
    fpk1_inic_reset(DEVICE(opaque));
}

static void fpk1_inic_init(Object *obj)
{
    Fpk1InicState *s = FPK1_INIC(obj);

    g_queue_init(&s->tx);
    qdev_init_gpio_out_named(DEVICE(obj), &s->int_n, "int", 1);
    qdev_init_gpio_in_named(DEVICE(obj), fpk1_inic_reset_in, "reset", 1);
}

static void fpk1_inic_class_init(ObjectClass *klass, const void *data)
{
    DeviceClass *dc = DEVICE_CLASS(klass);
    I2CSlaveClass *k = I2C_SLAVE_CLASS(klass);

    k->event = fpk1_inic_event;
    k->recv = fpk1_inic_recv;
    k->send = fpk1_inic_send;
    device_class_set_legacy_reset(dc, fpk1_inic_reset);
}

static const TypeInfo fpk1_inic_info = {
    .name          = TYPE_FPK1_INIC,
    .parent        = TYPE_I2C_SLAVE,
    .instance_size = sizeof(Fpk1InicState),
    .instance_init = fpk1_inic_init,
    .class_init    = fpk1_inic_class_init,
};

static void fpk1_inic_register(void)
{
    type_register_static(&fpk1_inic_info);
}

type_init(fpk1_inic_register)
