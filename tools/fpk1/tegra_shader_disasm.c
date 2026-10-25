/*
 * Disassemble the GR3D program inside an NVIDIA platform shader binary
 * (GL_NVIDIA_PLATFORM_BINARY_NV, as captured by glhost in /tmp/mhi2-shader-*.bin)
 * with grate's libcgc. The binary embeds a host1x GR3D stream: vertex programs
 * are uploaded through method 0x206, fragment programs start at method 0x541.
 *
 * Build against a grate checkout (https://github.com/grate-driver/grate):
 *   cc -w -I$GRATE/include -I$GRATE/src/libcgc -o tegra_shader_disasm \
 *      tools/fpk1/tegra_shader_disasm.c $GRATE/src/libcgc/stream.c \
 *      $GRATE/src/libcgc/instruction.c $GRATE/src/libcgc/dummy.c
 */
#include "shader.c"

int main(int argc, char **argv)
{
    static uint8_t data[1 << 16];
    FILE *f = argc == 2 ? fopen(argv[1], "rb") : NULL;
    if (!f) {
        fprintf(stderr, "usage: %s shader.bin\n", argv[0]);
        return 2;
    }
    size_t count = fread(data, 1, sizeof(data), f) / 4;
    fclose(f);
    uint32_t *w = (uint32_t *)data;
    for (size_t i = 0; i < count; i++) {
        uint32_t op = w[i] >> 28, method = (w[i] >> 16) & 0xfff;
        if (op == 2 && method == 0x206) {
            size_t words = w[i] & 0xffff;
            static uint8_t buf[sizeof(struct cgc_header) + 4096];
            struct cgc_header *h = (struct cgc_header *)buf;
            if (i + 1 + words > count || words * 4 > 4096)
                return 1;
            h->binary_offset = sizeof(*h);
            h->binary_size = words * 4;
            memcpy(buf + sizeof(*h), &w[i + 1], words * 4);
            struct cgc_shader shader = { .type = CGC_SHADER_VERTEX, .binary = buf };
            vertex_shader_disassemble(&shader, stdout);
            return 0;
        }
        if ((op == 1 || op == 2) && method == 0x541) {
            fragment_shader_disassemble(&w[i], (count - i) * 4, 0);
            return 0;
        }
    }
    fprintf(stderr, "no GR3D program upload found\n");
    return 1;
}
