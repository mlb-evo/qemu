# FPK1 GLES translations for glhost

Files are `<fnv1a-64 hash>-<size>.{glsl,blend}` as read by `glhost` from
`MHI2_SHADER_CACHE` for NVIDIA binaries without an entry in
`tools/mhi2/glforward/host/known_shaders.h`. `.blend` holds the glhost blend
mode (0 none, 1 premultiplied source-over baked into the Tegra program).

| Hash | Size | Owner | Status |
| --- | --- | --- | --- |
| c15b5c368e434418 | 956 | 2D compositor vertex (vPosition, aspect, quad, rotation, texRect), used by kdgui_2dmgr and grengme | transcribed from `tegra_shader_disasm` output; positions, rotation and texRect confirmed by grengme's rendered service menu |
| 23522ab1913cc1e6 | 948 | 2D compositor fragment (texCoord, alphaTex, modulateColor, texture) | `alphaTex` is a bool set with glUniform1i (1 for GL_ALPHA glyphs); output is premultiplied for blend mode 1; glyphs, icons and lines match grengme's expected menu |
| f9b134a4613cf687 | 816 | EAL `Materials/displaySupervisor` fragment (vTexCoord, Color, LayerRenderTexture) | from `tegra_shader_disasm`: pass 1 `tex.r * c3` and alpha 1.0, pass 2 times c0..c2, no render-target load (blend 0); assumes ALU r6/r7 are the stored r2/r3 as in the known EAL programs. Not yet seen rendered (gtf2 does not draw) |
