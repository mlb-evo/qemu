## IPC callback MFL entry-point proof (stock GTF2)

The callback at 0x696f4c is virtual slot 28 (zero-based) in the vtable at 0x88e6b8: the literal pointer at 0x88e728 equals 0x696f4c. Constructor 0x6977a4 loads literal 0x88e6b0 from 0x697800, installs base+8 (0x88e6b8) at object+0, and also initializes secondary vptrs. Thus slot ownership is verified by constructor and vtable bytes, not inferred from diagnostic text.

Disassembly 0x696f4c..0x696fbc shows the callback receives a wrapper in r1 and dereferences its data pointer at [r1+4]. It reads payload[5] to call 0x131390 with DP 0x02000224; reads payload[0], [1], [2], [3] and forwards the four bytes to 0x18bb88; reads payload[5] again for 0x1a5e10 (MFL variant) and 0x1d7f4c (persistent normalization). The callback itself does not expose the symbolic IPC method name, and the payload structure is not yet identified from proxy IDL. Slot 28 is an index in the GTF2 callback vtable, not necessarily a protocol method number or message ID.

Nearby callback slots: 26=0x696fc0, 27=0x694524, 28=0x696f4c, 29=0x696f24, 30=0x693760. Next work: recover the proxy library's corresponding callback invocation site and argument marshalling, and distinguish interface vtable indices from protocol selector IDs. Static analysis only.
