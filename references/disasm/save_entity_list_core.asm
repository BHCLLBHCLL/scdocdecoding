   1811d7b50:	48 8b c4             	mov    rax,rsp
   1811d7b53:	57                   	push   rdi
   1811d7b54:	48 81 ec 40 01 00 00 	sub    rsp,0x140
   1811d7b5b:	48 c7 40 88 fe ff ff 	mov    QWORD PTR [rax-0x78],0xfffffffffffffffe
   1811d7b62:	ff 
   1811d7b63:	48 89 58 08          	mov    QWORD PTR [rax+0x8],rbx
   1811d7b67:	48 89 70 10          	mov    QWORD PTR [rax+0x10],rsi
   1811d7b6b:	48 8b da             	mov    rbx,rdx
   1811d7b6e:	48 8b f1             	mov    rsi,rcx
   1811d7b71:	33 ff                	xor    edi,edi
   1811d7b73:	89 7c 24 30          	mov    DWORD PTR [rsp+0x30],edi
   1811d7b77:	33 c9                	xor    ecx,ecx
   1811d7b79:	e8 02 ab f4 fe       	call   0x180122680
   1811d7b7e:	45 33 c0             	xor    r8d,r8d
   1811d7b81:	33 d2                	xor    edx,edx
   1811d7b83:	48 8d 4c 24 68       	lea    rcx,[rsp+0x68]
   1811d7b88:	e8 63 18 f7 ff       	call   0x1811493f0
   1811d7b8d:	90                   	nop
   1811d7b8e:	48 8d 8c 24 88 00 00 	lea    rcx,[rsp+0x88]
   1811d7b95:	00 
   1811d7b96:	e8 85 cd 26 00       	call   0x181444920
   1811d7b9b:	90                   	nop
   1811d7b9c:	89 bc 24 60 01 00 00 	mov    DWORD PTR [rsp+0x160],edi
   1811d7ba3:	89 bc 24 98 00 00 00 	mov    DWORD PTR [rsp+0x98],edi
   1811d7baa:	0f 57 c0             	xorps  xmm0,xmm0
   1811d7bad:	f3 0f 7f 84 24 a0 00 	movdqu XMMWORD PTR [rsp+0xa0],xmm0
   1811d7bb4:	00 00 
   1811d7bb6:	89 bc 24 b0 00 00 00 	mov    DWORD PTR [rsp+0xb0],edi
   1811d7bbd:	48 89 7c 24 48       	mov    QWORD PTR [rsp+0x48],rdi
   1811d7bc2:	89 7c 24 50          	mov    DWORD PTR [rsp+0x50],edi
   1811d7bc6:	48 c7 44 24 54 01 00 	mov    QWORD PTR [rsp+0x54],0x1
   1811d7bcd:	00 00 
   1811d7bcf:	c7 84 24 b8 00 00 00 	mov    DWORD PTR [rsp+0xb8],0x1
   1811d7bd6:	01 00 00 00 
   1811d7bda:	48 8d 44 24 68       	lea    rax,[rsp+0x68]
   1811d7bdf:	48 89 84 24 c0 00 00 	mov    QWORD PTR [rsp+0xc0],rax
   1811d7be6:	00 
   1811d7be7:	e8 84 18 fa ff       	call   0x181179470
   1811d7bec:	89 84 24 c8 00 00 00 	mov    DWORD PTR [rsp+0xc8],eax
   1811d7bf3:	8d 4f 01             	lea    ecx,[rdi+0x1]
   1811d7bf6:	e8 45 18 fa ff       	call   0x181179440
   1811d7bfb:	33 c9                	xor    ecx,ecx
   1811d7bfd:	e8 7e 09 f8 ff       	call   0x181158580
   1811d7c02:	90                   	nop
   1811d7c03:	e8 58 c5 f4 fe       	call   0x180124160
   1811d7c08:	e8 23 b6 f4 fe       	call   0x180123230
   1811d7c0d:	48 8b 08             	mov    rcx,QWORD PTR [rax]
   1811d7c10:	48 89 4c 24 50       	mov    QWORD PTR [rsp+0x50],rcx
   1811d7c15:	c7 44 24 58 01 00 00 	mov    DWORD PTR [rsp+0x58],0x1
   1811d7c1c:	00 
   1811d7c1d:	e8 0e b6 f4 fe       	call   0x180123230
   1811d7c22:	c7 00 01 00 00 00    	mov    DWORD PTR [rax],0x1
   1811d7c28:	48 8b cb             	mov    rcx,rbx
   1811d7c2b:	e8 b0 bc fa ff       	call   0x1811838e0
   1811d7c30:	48 8b cb             	mov    rcx,rbx
   1811d7c33:	e8 68 b2 fa ff       	call   0x181182ea0
   1811d7c38:	48 8d 4c 24 40       	lea    rcx,[rsp+0x40]
   1811d7c3d:	e8 ae 07 ff ff       	call   0x1811c83f0
   1811d7c42:	90                   	nop
   1811d7c43:	33 d2                	xor    edx,edx
   1811d7c45:	48 8d 8c 24 68 01 00 	lea    rcx,[rsp+0x168]
   1811d7c4c:	00 
   1811d7c4d:	e8 ce 8a 34 00       	call   0x181520720
   1811d7c52:	90                   	nop
   1811d7c53:	48 8b d3             	mov    rdx,rbx
   1811d7c56:	48 8d 4c 24 38       	lea    rcx,[rsp+0x38]
   1811d7c5b:	e8 00 09 ff ff       	call   0x1811c8560
   1811d7c60:	90                   	nop
   1811d7c61:	e8 9a 38 1f 00       	call   0x1813cb500
   1811d7c66:	48 85 c0             	test   rax,rax
   1811d7c69:	74 0f                	je     0x1811d7c7a
   1811d7c6b:	4c 8b 00             	mov    r8,QWORD PTR [rax]
   1811d7c6e:	48 8d 54 24 38       	lea    rdx,[rsp+0x38]
   1811d7c73:	48 8b c8             	mov    rcx,rax
   1811d7c76:	41 ff 50 08          	call   QWORD PTR [r8+0x8]
   1811d7c7a:	48 8d 44 24 60       	lea    rax,[rsp+0x60]
   1811d7c7f:	48 89 44 24 20       	mov    QWORD PTR [rsp+0x20],rax
   1811d7c84:	4c 8d 4c 24 40       	lea    r9,[rsp+0x40]
   1811d7c89:	45 33 c0             	xor    r8d,r8d
   1811d7c8c:	48 8d 54 24 38       	lea    rdx,[rsp+0x38]
   1811d7c91:	48 8b ce             	mov    rcx,rsi
   1811d7c94:	e8 87 e8 ff ff       	call   0x1811d6520
   1811d7c99:	89 44 24 30          	mov    DWORD PTR [rsp+0x30],eax
   1811d7c9d:	e8 5e 38 1f 00       	call   0x1813cb500
   1811d7ca2:	48 85 c0             	test   rax,rax
   1811d7ca5:	74 0f                	je     0x1811d7cb6
   1811d7ca7:	4c 8b 00             	mov    r8,QWORD PTR [rax]
   1811d7caa:	48 8d 54 24 38       	lea    rdx,[rsp+0x38]
   1811d7caf:	48 8b c8             	mov    rcx,rax
   1811d7cb2:	41 ff 50 10          	call   QWORD PTR [r8+0x10]
   1811d7cb6:	48 8d 0d ab 6c 5b 02 	lea    rcx,[rip+0x25b6cab]        # 0x18378e968
   1811d7cbd:	e8 4e ca fb fe       	call   0x180194710
   1811d7cc2:	48 83 38 00          	cmp    QWORD PTR [rax],0x0
   1811d7cc6:	75 04                	jne    0x1811d7ccc
   1811d7cc8:	8b c7                	mov    eax,edi
   1811d7cca:	eb 1d                	jmp    0x1811d7ce9
   1811d7ccc:	48 8d 0d 95 6c 5b 02 	lea    rcx,[rip+0x25b6c95]        # 0x18378e968
   1811d7cd3:	e8 38 ca fb fe       	call   0x180194710
   1811d7cd8:	48 8b 08             	mov    rcx,QWORD PTR [rax]
   1811d7cdb:	8b c7                	mov    eax,edi
   1811d7cdd:	83 79 0c 01          	cmp    DWORD PTR [rcx+0xc],0x1
   1811d7ce1:	77 06                	ja     0x1811d7ce9
   1811d7ce3:	39 79 10             	cmp    DWORD PTR [rcx+0x10],edi
   1811d7ce6:	0f 95 c0             	setne  al
   1811d7ce9:	85 c0                	test   eax,eax
   1811d7ceb:	75 1d                	jne    0x1811d7d0a
   1811d7ced:	e8 8e 3c 27 00       	call   0x18144b980
   1811d7cf2:	83 38 6a             	cmp    DWORD PTR [rax],0x6a
   1811d7cf5:	7c 13                	jl     0x1811d7d0a
   1811d7cf7:	45 33 c0             	xor    r8d,r8d
   1811d7cfa:	41 8d 50 01          	lea    edx,[r8+0x1]
   1811d7cfe:	48 8d 0d 63 3b 7f 01 	lea    rcx,[rip+0x17f3b63]        # 0x1829cb868
   1811d7d05:	e8 66 34 27 00       	call   0x18144b170
   1811d7d0a:	48 8d 4c 24 40       	lea    rcx,[rsp+0x40]
   1811d7d0f:	e8 bc a4 ef ff       	call   0x1810d21d0
   1811d7d14:	e8 a7 66 32 00       	call   0x1814fe3c0
   1811d7d19:	90                   	nop
   1811d7d1a:	48 8d 4c 24 38       	lea    rcx,[rsp+0x38]
   1811d7d1f:	e8 ec 06 ff ff       	call   0x1811c8410
   1811d7d24:	90                   	nop
   1811d7d25:	48 8d 8c 24 68 01 00 	lea    rcx,[rsp+0x168]
   1811d7d2c:	00 
   1811d7d2d:	e8 2e 8a 34 00       	call   0x181520760
   1811d7d32:	90                   	nop
   1811d7d33:	48 8d 4c 24 40       	lea    rcx,[rsp+0x40]
   1811d7d38:	e8 d3 06 ff ff       	call   0x1811c8410
   1811d7d3d:	90                   	nop
   1811d7d3e:	eb 46                	jmp    0x1811d7d86
   1811d7d40:	8b 9c 24 d8 00 00 00 	mov    ebx,DWORD PTR [rsp+0xd8]
   1811d7d47:	85 db                	test   ebx,ebx
   1811d7d49:	74 39                	je     0x1811d7d84
   1811d7d4b:	48 8d 4c 24 48       	lea    rcx,[rsp+0x48]
   1811d7d50:	e8 eb 8e f8 ff       	call   0x181160c40
   1811d7d55:	4c 8b c0             	mov    r8,rax
   1811d7d58:	8b d3                	mov    edx,ebx
   1811d7d5a:	48 8d 8c 24 f8 00 00 	lea    rcx,[rsp+0xf8]
   1811d7d61:	00 
   1811d7d62:	e8 89 16 f7 ff       	call   0x1811493f0
   1811d7d67:	90                   	nop
   1811d7d68:	48 8b d0             	mov    rdx,rax
   1811d7d6b:	48 8d 4c 24 68       	lea    rcx,[rsp+0x68]
   1811d7d70:	e8 6b 18 f7 ff       	call   0x1811495e0
   1811d7d75:	90                   	nop
   1811d7d76:	48 8d 8c 24 f8 00 00 	lea    rcx,[rsp+0xf8]
   1811d7d7d:	00 
   1811d7d7e:	e8 fd 16 f7 ff       	call   0x181149480
   1811d7d83:	90                   	nop
   1811d7d84:	33 ff                	xor    edi,edi
   1811d7d86:	8b 9c 24 c8 00 00 00 	mov    ebx,DWORD PTR [rsp+0xc8]
   1811d7d8d:	85 db                	test   ebx,ebx
   1811d7d8f:	40 0f 94 c7          	sete   dil
   1811d7d93:	44 8b c7             	mov    r8d,edi
   1811d7d96:	33 d2                	xor    edx,edx
   1811d7d98:	48 8d 4c 24 68       	lea    rcx,[rsp+0x68]
   1811d7d9d:	e8 ae 08 f8 ff       	call   0x181158650
   1811d7da2:	8b cb                	mov    ecx,ebx
   1811d7da4:	e8 97 16 fa ff       	call   0x181179440
   1811d7da9:	90                   	nop
   1811d7daa:	e8 81 b4 f4 fe       	call   0x180123230
   1811d7daf:	48 8b 4c 24 50       	mov    rcx,QWORD PTR [rsp+0x50]
   1811d7db4:	48 89 08             	mov    QWORD PTR [rax],rcx
   1811d7db7:	e8 d4 c3 f4 fe       	call   0x180124190
   1811d7dbc:	e8 9f c4 f4 fe       	call   0x180124260
   1811d7dc1:	85 c0                	test   eax,eax
   1811d7dc3:	74 12                	je     0x1811d7dd7
   1811d7dc5:	48 8b 54 24 48       	mov    rdx,QWORD PTR [rsp+0x48]
   1811d7dca:	8b 8c 24 60 01 00 00 	mov    ecx,DWORD PTR [rsp+0x160]
   1811d7dd1:	e8 8a b3 f4 fe       	call   0x180123160
   1811d7dd6:	90                   	nop
   1811d7dd7:	48 8b 8c 24 a0 00 00 	mov    rcx,QWORD PTR [rsp+0xa0]
   1811d7dde:	00 
   1811d7ddf:	48 85 c9             	test   rcx,rcx
   1811d7de2:	74 05                	je     0x1811d7de9
   1811d7de4:	e8 47 a6 f4 fe       	call   0x180122430
   1811d7de9:	45 33 c9             	xor    r9d,r9d
   1811d7dec:	45 33 c0             	xor    r8d,r8d
   1811d7def:	48 8d 54 24 68       	lea    rdx,[rsp+0x68]
   1811d7df4:	48 8d 8c 24 88 00 00 	lea    rcx,[rsp+0x88]
   1811d7dfb:	00 
   1811d7dfc:	e8 cf cb 26 00       	call   0x1814449d0
   1811d7e01:	48 8d 4c 24 68       	lea    rcx,[rsp+0x68]
   1811d7e06:	e8 35 43 f0 ff       	call   0x1810dc140
   1811d7e0b:	90                   	nop
   1811d7e0c:	48 8d 8c 24 88 00 00 	lea    rcx,[rsp+0x88]
   1811d7e13:	00 
   1811d7e14:	e8 57 cb 26 00       	call   0x181444970
   1811d7e19:	90                   	nop
   1811d7e1a:	48 8d 4c 24 68       	lea    rcx,[rsp+0x68]
   1811d7e1f:	e8 5c 16 f7 ff       	call   0x181149480
   1811d7e24:	8b 44 24 30          	mov    eax,DWORD PTR [rsp+0x30]
   1811d7e28:	4c 8d 9c 24 40 01 00 	lea    r11,[rsp+0x140]
   1811d7e2f:	00 
   1811d7e30:	49 8b 5b 10          	mov    rbx,QWORD PTR [r11+0x10]
   1811d7e34:	49 8b 73 18          	mov    rsi,QWORD PTR [r11+0x18]
   1811d7e38:	49 8b e3             	mov    rsp,r11
   1811d7e3b:	5f                   	pop    rdi
   1811d7e3c:	c3                   	ret
