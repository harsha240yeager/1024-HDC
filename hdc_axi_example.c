#include "xil_io.h"
#include "xil_printf.h"
#include "sleep.h"

#define HDC_AXI_BASEADDR   0x43C00000U

#define HDC_REG_CONTROL    0x000U
#define HDC_REG_STATUS     0x004U
#define HDC_REG_MODE       0x008U
#define HDC_REG_PARAM      0x00CU
#define HDC_REG_INPUT      0x100U
#define HDC_REG_BIND       0x200U
#define HDC_REG_OUTPUT     0x300U

#define HDC_CONTROL_START      0x00000001U
#define HDC_CONTROL_CLEAR_DONE 0x00000004U

#define HDC_STATUS_DONE    0x00000001U
#define HDC_STATUS_BUSY    0x00000002U

#define HDC_VECTOR_WORDS   32U

static void hdc_write_vector(u32 base_addr, u32 reg_base, const u32 *data_words)
{
    u32 i;

    for (i = 0; i < HDC_VECTOR_WORDS; ++i) {
        Xil_Out32(base_addr + reg_base + (i * 4U), data_words[i]);
    }
}

static void hdc_read_vector(u32 base_addr, u32 reg_base, u32 *data_words)
{
    u32 i;

    for (i = 0; i < HDC_VECTOR_WORDS; ++i) {
        data_words[i] = Xil_In32(base_addr + reg_base + (i * 4U));
    }
}

static int hdc_wait_done(u32 base_addr, u32 timeout_cycles)
{
    u32 status;

    while (timeout_cycles-- > 0U) {
        status = Xil_In32(base_addr + HDC_REG_STATUS);
        if ((status & HDC_STATUS_DONE) != 0U) {
            return 0;
        }
        usleep(100U);
    }

    return -1;
}

int main(void)
{
    u32 input_vec[HDC_VECTOR_WORDS];
    u32 bind_vec[HDC_VECTOR_WORDS];
    u32 output_vec[HDC_VECTOR_WORDS];
    u32 i;
    int rc;

    xil_printf("HDC AXI example start\r\n");

    for (i = 0; i < HDC_VECTOR_WORDS; ++i) {
        input_vec[i] = 0x10000000U + i;
        bind_vec[i] = 0xAAAA0000U ^ (i * 0x1111U);
        output_vec[i] = 0U;
    }

    /*
     * Clear stale done status before loading a new job.
     */
    Xil_Out32(HDC_AXI_BASEADDR + HDC_REG_CONTROL, HDC_CONTROL_CLEAR_DONE);

    hdc_write_vector(HDC_AXI_BASEADDR, HDC_REG_INPUT, input_vec);
    hdc_write_vector(HDC_AXI_BASEADDR, HDC_REG_BIND, bind_vec);

    /*
     * Example configuration:
     *   perm_mode  = 2'b10  (full rotate)
     *   perm_param = 73
     */
    Xil_Out32(HDC_AXI_BASEADDR + HDC_REG_MODE, 2U);
    Xil_Out32(HDC_AXI_BASEADDR + HDC_REG_PARAM, 73U);

    /*
     * Kick off one transaction.
     */
    Xil_Out32(HDC_AXI_BASEADDR + HDC_REG_CONTROL, HDC_CONTROL_START);

    rc = hdc_wait_done(HDC_AXI_BASEADDR, 100000U);
    if (rc != 0) {
        xil_printf("ERROR: timed out waiting for done\r\n");
        return -1;
    }

    hdc_read_vector(HDC_AXI_BASEADDR, HDC_REG_OUTPUT, output_vec);

    xil_printf("Output words [0..7]:\r\n");
    for (i = 0; i < 8U; ++i) {
        xil_printf("  out[%02lu] = 0x%08lx\r\n", (unsigned long)i, (unsigned long)output_vec[i]);
    }

    Xil_Out32(HDC_AXI_BASEADDR + HDC_REG_CONTROL, HDC_CONTROL_CLEAR_DONE);

    xil_printf("HDC AXI example complete\r\n");
    return 0;
}
