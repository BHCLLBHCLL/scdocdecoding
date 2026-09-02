   18116b010:	48 8b c4             	mov    rax,rsp
   18116b013:	48 89 48 08          	mov    QWORD PTR [rax+0x8],rcx
   18116b017:	57                   	push   rdi
   18116b018:	41 56                	push   r14
   18116b01a:	41 57                	push   r15
   18116b01c:	48 81 ec 00 01 00 00 	sub    rsp,0x100
   18116b023:	48 c7 40 80 fe ff ff 	mov    QWORD PTR [rax-0x80],0xfffffffffffffffe
   18116b02a:	ff 
   18116b02b:	48 89 58 10          	mov    QWORD PTR [rax+0x10],rbx
   18116b02f:	48 89 70 18          	mov    QWORD PTR [rax+0x18],rsi
   18116b033:	49 8b f1             	mov    rsi,r9
   18116b036:	45 8b f8             	mov    r15d,r8d
   18116b039:	4c 8b f2             	mov    r14,rdx
   18116b03c:	48 8b f9             	mov    rdi,rcx
   18116b03f:	33 db                	xor    ebx,ebx
   18116b041:	89 5c 24 28          	mov    DWORD PTR [rsp+0x28],ebx
   18116b045:	48 8d 0d b4 0f 84 01 	lea    rcx,[rip+0x1840fb4]        # 0x1829ac000
   18116b04c:	e8 ef 71 fd fe       	call   0x180142240
   18116b051:	85 c0                	test   eax,eax
   18116b053:	74 29                	je     0x18116b07e
   18116b055:	33 d2                	xor    edx,edx
   18116b057:	48 8d 0d fa 94 5f 02 	lea    rcx,[rip+0x25f94fa]        # 0x183764558
   18116b05e:	e8 3d 8a fb fe       	call   0x180123aa0
   18116b063:	8b d0                	mov    edx,eax
   18116b065:	45 33 c0             	xor    r8d,r8d
   18116b068:	48 8b cf             	mov    rcx,rdi
   18116b06b:	e8 80 e3 fd ff       	call   0x1811493f0
   18116b070:	90                   	nop
   18116b071:	c7 44 24 28 01 00 00 	mov    DWORD PTR [rsp+0x28],0x1
   18116b078:	00 
   18116b079:	e9 12 02 00 00       	jmp    0x18116b290
   18116b07e:	33 c9                	xor    ecx,ecx
   18116b080:	e8 fb 75 fb fe       	call   0x180122680
   18116b085:	45 33 c0             	xor    r8d,r8d
   18116b088:	33 d2                	xor    edx,edx
   18116b08a:	48 8d 4c 24 78       	lea    rcx,[rsp+0x78]
   18116b08f:	e8 5c e3 fd ff       	call   0x1811493f0
   18116b094:	90                   	nop
   18116b095:	48 8d 4c 24 68       	lea    rcx,[rsp+0x68]
   18116b09a:	e8 81 98 2d 00       	call   0x181444920
   18116b09f:	90                   	nop
   18116b0a0:	89 5c 24 20          	mov    DWORD PTR [rsp+0x20],ebx
   18116b0a4:	89 5c 24 48          	mov    DWORD PTR [rsp+0x48],ebx
   18116b0a8:	0f 57 c0             	xorps  xmm0,xmm0
   18116b0ab:	f3 0f 7f 44 24 50    	movdqu XMMWORD PTR [rsp+0x50],xmm0
   18116b0b1:	89 5c 24 60          	mov    DWORD PTR [rsp+0x60],ebx
   18116b0b5:	48 89 5c 24 30       	mov    QWORD PTR [rsp+0x30],rbx
   18116b0ba:	89 5c 24 38          	mov    DWORD PTR [rsp+0x38],ebx
   18116b0be:	48 c7 44 24 3c 01 00 	mov    QWORD PTR [rsp+0x3c],0x1
   18116b0c5:	00 00 
   18116b0c7:	e8 c4 6b 01 00       	call   0x181181c90
   18116b0cc:	e8 8f 90 fb fe       	call   0x180124160
   18116b0d1:	e8 5a 81 fb fe       	call   0x180123230
   18116b0d6:	48 8b 08             	mov    rcx,QWORD PTR [rax]
   18116b0d9:	48 89 4c 24 38       	mov    QWORD PTR [rsp+0x38],rcx
   18116b0de:	c7 44 24 40 01 00 00 	mov    DWORD PTR [rsp+0x40],0x1
   18116b0e5:	00 
   18116b0e6:	e8 45 81 fb fe       	call   0x180123230
   18116b0eb:	c7 00 01 00 00 00    	mov    DWORD PTR [rax],0x1
   18116b0f1:	48 8b 8c 24 40 01 00 	mov    rcx,QWORD PTR [rsp+0x140]
   18116b0f8:	00 
   18116b0f9:	48 85 c9             	test   rcx,rcx
   18116b0fc:	74 08                	je     0x18116b106
   18116b0fe:	48 8b 01             	mov    rax,QWORD PTR [rcx]
   18116b101:	ff 50 20             	call   QWORD PTR [rax+0x20]
   18116b104:	eb 03                	jmp    0x18116b109
   18116b106:	48 8b c3             	mov    rax,rbx
   18116b109:	48 8b d0             	mov    rdx,rax
   18116b10c:	48 8d 4c 24 24       	lea    rcx,[rsp+0x24]
   18116b111:	e8 da 74 05 ff       	call   0x1801c25f0
   18116b116:	90                   	nop
   18116b117:	e8 f4 ea ff ff       	call   0x181169c10
   18116b11c:	85 c0                	test   eax,eax
   18116b11e:	74 35                	je     0x18116b155
   18116b120:	48 8b ce             	mov    rcx,rsi
   18116b123:	e8 b8 d8 05 00       	call   0x1811c89e0
   18116b128:	48 85 c0             	test   rax,rax
   18116b12b:	74 19                	je     0x18116b146
   18116b12d:	41 b0 01             	mov    r8b,0x1
   18116b130:	41 0f b6 d0          	movzx  edx,r8b
   18116b134:	48 8b c8             	mov    rcx,rax
   18116b137:	e8 74 d8 fe ff       	call   0x1811589b0
   18116b13c:	48 8b ce             	mov    rcx,rsi
   18116b13f:	e8 dc d8 05 00       	call   0x1811c8a20
   18116b144:	eb e2                	jmp    0x18116b128
   18116b146:	48 8d 15 e3 0e 84 01 	lea    rdx,[rip+0x1840ee3]        # 0x1829ac030
   18116b14d:	49 8b ce             	mov    rcx,r14
   18116b150:	e8 bb e7 fe ff       	call   0x181159910
   18116b155:	48 8b ce             	mov    rcx,rsi
   18116b158:	e8 53 0f 35 00       	call   0x1814bc0b0
   18116b15d:	4c 8b c6             	mov    r8,rsi
   18116b160:	41 8b d7             	mov    edx,r15d
   18116b163:	49 8b ce             	mov    rcx,r14
   18116b166:	e8 d5 c2 06 00       	call   0x1811d7440
   18116b16b:	85 c0                	test   eax,eax
   18116b16d:	74 04                	je     0x18116b173
   18116b16f:	8b c3                	mov    eax,ebx
   18116b171:	eb 0e                	jmp    0x18116b181
   18116b173:	33 d2                	xor    edx,edx
   18116b175:	48 8d 0d 0c 0c 62 02 	lea    rcx,[rip+0x2620c0c]        # 0x18378bd88
   18116b17c:	e8 1f 89 fb fe       	call   0x180123aa0
   18116b181:	45 33 c0             	xor    r8d,r8d
   18116b184:	8b d0                	mov    edx,eax
   18116b186:	48 8d 8c 24 a0 00 00 	lea    rcx,[rsp+0xa0]
   18116b18d:	00 
   18116b18e:	e8 5d e2 fd ff       	call   0x1811493f0
   18116b193:	90                   	nop
   18116b194:	48 8b d0             	mov    rdx,rax
   18116b197:	48 8d 4c 24 78       	lea    rcx,[rsp+0x78]
   18116b19c:	e8 3f e4 fd ff       	call   0x1811495e0
   18116b1a1:	90                   	nop
   18116b1a2:	48 8d 8c 24 a0 00 00 	lea    rcx,[rsp+0xa0]
   18116b1a9:	00 
   18116b1aa:	e8 d1 e2 fd ff       	call   0x181149480
   18116b1af:	90                   	nop
   18116b1b0:	48 8d 4c 24 24       	lea    rcx,[rsp+0x24]
   18116b1b5:	e8 b6 74 05 ff       	call   0x1801c2670
   18116b1ba:	90                   	nop
   18116b1bb:	eb 0c                	jmp    0x18116b1c9
   18116b1bd:	48 8b bc 24 20 01 00 	mov    rdi,QWORD PTR [rsp+0x120]
   18116b1c4:	00 
   18116b1c5:	8b 5c 24 24          	mov    ebx,DWORD PTR [rsp+0x24]
   18116b1c9:	85 db                	test   ebx,ebx
   18116b1cb:	74 43                	je     0x18116b210
   18116b1cd:	48 8d 4c 24 30       	lea    rcx,[rsp+0x30]
   18116b1d2:	e8 69 5a ff ff       	call   0x181160c40
   18116b1d7:	4c 8b c0             	mov    r8,rax
   18116b1da:	8b d3                	mov    edx,ebx
   18116b1dc:	48 8d 8c 24 a0 00 00 	lea    rcx,[rsp+0xa0]
   18116b1e3:	00 
   18116b1e4:	e8 07 e2 fd ff       	call   0x1811493f0
   18116b1e9:	90                   	nop
   18116b1ea:	48 8b d0             	mov    rdx,rax
   18116b1ed:	48 8d 4c 24 78       	lea    rcx,[rsp+0x78]
   18116b1f2:	e8 e9 e3 fd ff       	call   0x1811495e0
   18116b1f7:	90                   	nop
   18116b1f8:	48 8d 8c 24 a0 00 00 	lea    rcx,[rsp+0xa0]
   18116b1ff:	00 
   18116b200:	e8 7b e2 fd ff       	call   0x181149480
   18116b205:	90                   	nop
   18116b206:	eb 08                	jmp    0x18116b210
   18116b208:	48 8b bc 24 20 01 00 	mov    rdi,QWORD PTR [rsp+0x120]
   18116b20f:	00 
   18116b210:	83 7c 24 40 00       	cmp    DWORD PTR [rsp+0x40],0x0
   18116b215:	74 12                	je     0x18116b229
   18116b217:	e8 14 80 fb fe       	call   0x180123230
   18116b21c:	48 8b 4c 24 38       	mov    rcx,QWORD PTR [rsp+0x38]
   18116b221:	48 89 08             	mov    QWORD PTR [rax],rcx
   18116b224:	e8 67 8f fb fe       	call   0x180124190
   18116b229:	e8 32 90 fb fe       	call   0x180124260
   18116b22e:	85 c0                	test   eax,eax
   18116b230:	74 0f                	je     0x18116b241
   18116b232:	48 8b 54 24 30       	mov    rdx,QWORD PTR [rsp+0x30]
   18116b237:	8b 4c 24 20          	mov    ecx,DWORD PTR [rsp+0x20]
   18116b23b:	e8 20 7f fb fe       	call   0x180123160
   18116b240:	90                   	nop
   18116b241:	48 8b 4c 24 50       	mov    rcx,QWORD PTR [rsp+0x50]
   18116b246:	48 85 c9             	test   rcx,rcx
   18116b249:	74 05                	je     0x18116b250
   18116b24b:	e8 e0 71 fb fe       	call   0x180122430
   18116b250:	45 33 c9             	xor    r9d,r9d
   18116b253:	45 8d 41 01          	lea    r8d,[r9+0x1]
   18116b257:	48 8d 54 24 78       	lea    rdx,[rsp+0x78]
   18116b25c:	48 8d 4c 24 68       	lea    rcx,[rsp+0x68]
   18116b261:	e8 6a 97 2d 00       	call   0x1814449d0
   18116b266:	48 8d 54 24 78       	lea    rdx,[rsp+0x78]
   18116b26b:	48 8b cf             	mov    rcx,rdi
   18116b26e:	e8 bd e1 fd ff       	call   0x181149430
   18116b273:	c7 44 24 28 01 00 00 	mov    DWORD PTR [rsp+0x28],0x1
   18116b27a:	00 
   18116b27b:	48 8d 4c 24 68       	lea    rcx,[rsp+0x68]
   18116b280:	e8 eb 96 2d 00       	call   0x181444970
   18116b285:	90                   	nop
   18116b286:	48 8d 4c 24 78       	lea    rcx,[rsp+0x78]
   18116b28b:	e8 f0 e1 fd ff       	call   0x181149480
   18116b290:	48 8b c7             	mov    rax,rdi
   18116b293:	4c 8d 9c 24 00 01 00 	lea    r11,[rsp+0x100]
   18116b29a:	00 
   18116b29b:	49 8b 5b 28          	mov    rbx,QWORD PTR [r11+0x28]
   18116b29f:	49 8b 73 30          	mov    rsi,QWORD PTR [r11+0x30]
   18116b2a3:	49 8b e3             	mov    rsp,r11
   18116b2a6:	41 5f                	pop    r15
   18116b2a8:	41 5e                	pop    r14
   18116b2aa:	5f                   	pop    rdi
   18116b2ab:	c3                   	ret
   18116b2ac:	cc                   	int3
