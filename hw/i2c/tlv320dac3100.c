/*
 * TI TLV320DAC3100 audio DAC, I2C control port only (research stub).
 *
 * FPK1 audio_player configures the DAC on I2C1 at 0x18 and requests a reboot
 * when softReset() is not acknowledged. Registers are paged: register 0 of
 * every page selects the page, page 0 register 1 bit 0 is the self-clearing
 * software reset. The DAC/driver power flags (page 0 registers 37/38) follow
 * the corresponding power-up bits so polling for power-up completes. No audio
 * data path is modelled; I2S stays with the SoC.
 */

#include "qemu/osdep.h"
#include "qemu/log.h"
#include "qemu/module.h"
#include "hw/i2c/i2c.h"
#include "migration/vmstate.h"
#include "qom/object.h"

#define TYPE_TLV320DAC3100 "tlv320dac3100"
OBJECT_DECLARE_SIMPLE_TYPE(TLV320DAC3100State, TLV320DAC3100)

#define DAC_PAGES 16
#define DAC_PAGE_SIZE 128

struct TLV320DAC3100State {
    I2CSlave parent_obj;

    uint8_t regs[DAC_PAGES][DAC_PAGE_SIZE];
    uint8_t page;
    uint8_t ptr;
    bool addr_received;
};

static void tlv320dac3100_soft_reset(TLV320DAC3100State *s)
{
    memset(s->regs, 0, sizeof(s->regs));
    s->page = 0;
    /* Page 0 power-on defaults from the datasheet register map. */
    s->regs[0][0x03] = 0x02; /* OT flag is active low: no overtemperature */
    s->regs[0][0x05] = 0x11; /* PLL P=1, R=1 */
    s->regs[0][0x06] = 0x04; /* PLL J=4 */
    s->regs[0][0x0b] = 0x01; /* NDAC */
    s->regs[0][0x0c] = 0x01; /* MDAC */
    s->regs[0][0x0e] = 0x80; /* DOSR LSB */
    s->regs[0][0x3c] = 0x01; /* processing block PRB_P1 */
    s->regs[0][0x3f] = 0x14; /* DAC data path, both DACs powered down */
    s->regs[0][0x40] = 0x0c; /* both DACs muted */
    /* Page 1 output stage defaults. */
    s->regs[1][0x1f] = 0x04; /* HP drivers powered down */
    s->regs[1][0x20] = 0x06; /* class-D driver powered down */
    s->regs[1][0x28] = 0x02;
    s->regs[1][0x29] = 0x02;
    s->regs[1][0x2a] = 0x00;
    s->regs[1][0x2e] = 0x00;
}

static void tlv320dac3100_reset(DeviceState *dev)
{
    TLV320DAC3100State *s = TLV320DAC3100(dev);

    tlv320dac3100_soft_reset(s);
    s->ptr = 0;
    s->addr_received = false;
}

static uint8_t tlv320dac3100_read_reg(TLV320DAC3100State *s, uint8_t reg)
{
    if (reg == 0) {
        return s->page;
    }
    if (s->page == 0 && reg == 0x25) {
        /* DAC flag register 1: power state of DACs and output drivers. */
        uint8_t dac = s->regs[0][0x3f], hp = s->regs[1][0x1f];
        uint8_t spk = s->regs[1][0x20];
        return (dac & 0x80 ? 0x80 : 0) | (hp & 0x80 ? 0x20 : 0) |
               (spk & 0x80 ? 0x10 : 0) | (dac & 0x40 ? 0x08 : 0) |
               (hp & 0x40 ? 0x02 : 0) | (spk & 0x80 ? 0x01 : 0);
    }
    if (s->page == 0 && reg == 0x26) {
        /* DAC flag register 2: PGA gains have reached their targets. */
        return 0x11;
    }
    if (s->page >= DAC_PAGES || reg >= DAC_PAGE_SIZE) {
        return 0;
    }
    if (s->page == 0 && reg == 0x03) {
        return 0x02; /* read-only flag register */
    }
    if (s->page == 0 && reg == 0x43 && (s->regs[0][0x43] & 0x80)) {
        /* Headset detection enabled: report a load without microphone,
         * which audio_player takes as the speaker being present. */
        return (s->regs[0][0x43] & ~0x60) | 0x20;
    }
    return s->regs[s->page][reg];
}

static void tlv320dac3100_write_reg(TLV320DAC3100State *s, uint8_t reg,
                                    uint8_t val)
{
    if (reg == 0) {
        s->page = val;
        return;
    }
    if (s->page == 0 && reg == 1) {
        if (val & 1) {
            tlv320dac3100_soft_reset(s);
        }
        return;
    }
    if (s->page >= DAC_PAGES || reg >= DAC_PAGE_SIZE) {
        qemu_log_mask(LOG_UNIMP, "%s: write page %u reg 0x%02x <= 0x%02x\n",
                      TYPE_TLV320DAC3100, s->page, reg, val);
        return;
    }
    s->regs[s->page][reg] = val;
}

static int tlv320dac3100_event(I2CSlave *i2c, enum i2c_event event)
{
    TLV320DAC3100State *s = TLV320DAC3100(i2c);

    if (event == I2C_START_SEND) {
        s->addr_received = false;
    }
    return 0;
}

static uint8_t tlv320dac3100_recv(I2CSlave *i2c)
{
    TLV320DAC3100State *s = TLV320DAC3100(i2c);

    return tlv320dac3100_read_reg(s, s->ptr++);
}

static int tlv320dac3100_send(I2CSlave *i2c, uint8_t data)
{
    TLV320DAC3100State *s = TLV320DAC3100(i2c);

    if (!s->addr_received) {
        s->ptr = data;
        s->addr_received = true;
    } else {
        tlv320dac3100_write_reg(s, s->ptr++, data);
    }
    return 0;
}

static const VMStateDescription tlv320dac3100_vmstate = {
    .name = TYPE_TLV320DAC3100,
    .version_id = 1,
    .minimum_version_id = 1,
    .fields = (const VMStateField[]) {
        VMSTATE_I2C_SLAVE(parent_obj, TLV320DAC3100State),
        VMSTATE_UINT8_2DARRAY(regs, TLV320DAC3100State, DAC_PAGES, DAC_PAGE_SIZE),
        VMSTATE_UINT8(page, TLV320DAC3100State),
        VMSTATE_UINT8(ptr, TLV320DAC3100State),
        VMSTATE_BOOL(addr_received, TLV320DAC3100State),
        VMSTATE_END_OF_LIST()
    }
};

static void tlv320dac3100_class_init(ObjectClass *klass, const void *data)
{
    DeviceClass *dc = DEVICE_CLASS(klass);
    I2CSlaveClass *k = I2C_SLAVE_CLASS(klass);

    k->event = tlv320dac3100_event;
    k->recv = tlv320dac3100_recv;
    k->send = tlv320dac3100_send;
    device_class_set_legacy_reset(dc, tlv320dac3100_reset);
    dc->vmsd = &tlv320dac3100_vmstate;
}

static const TypeInfo tlv320dac3100_info = {
    .name          = TYPE_TLV320DAC3100,
    .parent        = TYPE_I2C_SLAVE,
    .instance_size = sizeof(TLV320DAC3100State),
    .class_init    = tlv320dac3100_class_init,
};

static void tlv320dac3100_register(void)
{
    type_register_static(&tlv320dac3100_info);
}

type_init(tlv320dac3100_register)
