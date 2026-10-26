#ifndef HW_MISC_TEGRA30_SLINK_H
#define HW_MISC_TEGRA30_SLINK_H

#include "qom/object.h"
#include "hw/core/sysbus.h"
#include "chardev/char-fe.h"

/*
 * Tegra30 SLINK controller in slave mode, as used by FPK1's libnvspislave for
 * the GSS<->KSS link.  The SPI master (KSS) is an external process on a
 * chardev; see tegra30_slink.c for the byte protocol.
 */
#define TYPE_TEGRA30_SLINK "tegra30-slink"
OBJECT_DECLARE_SIMPLE_TYPE(Tegra30SlinkState, TEGRA30_SLINK)

#define TEGRA30_SLINK_FIFO_BYTES 128

struct Tegra30SlinkState {
    /*< private >*/
    SysBusDevice parent_obj;
    /*< public >*/

    MemoryRegion iomem;
    qemu_irq irq;
    qemu_irq hsk_out;          /* master's handshake line into the GPIO block */
    CharFrontend chr;

    uint32_t command, command2, status, dma_ctl;
    bool armed, hsk_in;

    uint8_t tx[TEGRA30_SLINK_FIFO_BYTES];
    uint8_t rx[TEGRA30_SLINK_FIFO_BYTES];
    unsigned tx_len, rx_len, rx_pos;

    /* Incoming chardev message being assembled, and a deferred exchange. */
    uint8_t msg[2 + 255];
    unsigned msg_len;
    uint8_t xfer[255];
    unsigned xfer_len;
    bool xfer_pending;
};

#endif /* HW_MISC_TEGRA30_SLINK_H */
