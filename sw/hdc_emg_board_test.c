/*
 * hdc_emg_board_test.c — Phase 3 full EMG dataset replay scaffold.
 *
 * Placeholder: loads proto/mask, runs N windows from pre-exported vectors in
 * DDR (see scripts/export_emg_board_vectors.py). Accuracy vs Python recorded
 * via JTAG readback @ 0x00100300.
 *
 * Build after EMG vectors are exported to emg_board_vectors.h (not in repo).
 */

#include "hdc_core_regs.h"
#include "hdc_dma_stream.h"
#include "xil_cache.h"
#include "xil_printf.h"

#define EMG_RESULTS_BASE  0x00100300U
#define EMG_MAGIC           0xBEC00005U
#define EMG_STATUS_DONE     1U

#ifndef EMG_BOARD_WINDOWS
#define EMG_BOARD_WINDOWS 0U
#endif

int main(void)
{
    xil_printf("==================================================\r\n");
    xil_printf("HDC EMG board replay (Phase 3 scaffold)\r\n");
    xil_printf("==================================================\r\n");

#if EMG_BOARD_WINDOWS == 0
    xil_printf("No EMG vectors linked. Run:\r\n");
    xil_printf("  python3 scripts/export_emg_board_vectors.py\r\n");
    xil_printf("Then rebuild with emg_board_vectors.h\r\n");
    Xil_Out32(EMG_RESULTS_BASE + 0x00, EMG_MAGIC);
    Xil_Out32(EMG_RESULTS_BASE + 0x04, 0U);
    Xil_DCacheFlushRange((INTPTR)EMG_RESULTS_BASE, 16U);
#else
    xil_printf("EMG replay not yet wired — export vectors first.\r\n");
#endif

    while (1)
        ;

    return 0;
}
