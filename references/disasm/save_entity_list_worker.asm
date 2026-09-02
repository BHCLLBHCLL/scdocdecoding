   1811d7440:	48 8b c4             	mov    rax,rsp
   1811d7443:	57                   	push   rdi
   1811d7444:	41 56                	push   r14
   1811d7446:	41 57                	push   r15
   1811d7448:	48 81 ec 20 01 00 00 	sub    rsp,0x120
   1811d744f:	48 c7 40 80 fe ff ff 	mov    QWORD PTR [rax-0x80],0xfffffffffffffffe
   1811d7456:	ff 
   1811d7457:	48 89 58 08          	mov    QWORD PTR [rax+0x8],rbx
   1811d745b:	48 89 70 18          	mov    QWORD PTR [rax+0x18],rsi
   1811d745f:	49 8b d8             	mov    rbx,r8
   1811d7462:	44 8b f2             	mov    r14d,edx
   1811d7465:	4c 8b f9             	mov    r15,rcx
   1811d7468:	85 d2                	test   edx,edx
   1811d746a:	0f 85 bd 00 00 00    	jne    0x1811d752d
   1811d7470:	48 8d 0d 31 74 5b 02 	lea    rcx,[rip+0x25b7431]        # 0x18378e8a8
   1811d7477:	e8 94 d2 fb fe       	call   0x180194710
   1811d747c:	48 83 38 00          	cmp    QWORD PTR [rax],0x0
   1811d7480:	75 06                	jne    0x1811d7488
   1811d7482:	33 f6                	xor    esi,esi
   1811d7484:	8b c6                	mov    eax,esi
   1811d7486:	eb 1f                	jmp    0x1811d74a7
   1811d7488:	48 8d 0d 19 74 5b 02 	lea    rcx,[rip+0x25b7419]        # 0x18378e8a8
   1811d748f:	e8 7c d2 fb fe       	call   0x180194710
   1811d7494:	48 8b 08             	mov    rcx,QWORD PTR [rax]
   1811d7497:	33 f6                	xor    esi,esi
   1811d7499:	8b c6                	mov    eax,esi
   1811d749b:	83 79 0c 01          	cmp    DWORD PTR [rcx+0xc],0x1
   1811d749f:	77 06                	ja     0x1811d74a7
   1811d74a1:	39 71 10             	cmp    DWORD PTR [rcx+0x10],esi
   1811d74a4:	0f 95 c0             	setne  al
   1811d74a7:	85 c0                	test   eax,eax
   1811d74a9:	0f 84 80 00 00 00    	je     0x1811d752f
   1811d74af:	48 8d 05 22 74 5b 02 	lea    rax,[rip+0x25b7422]        # 0x18378e8d8
   1811d74b6:	48 89 44 24 28       	mov    QWORD PTR [rsp+0x28],rax
   1811d74bb:	c7 44 24 20 7d 04 00 	mov    DWORD PTR [rsp+0x20],0x47d
   1811d74c2:	00 
   1811d74c3:	4c 8d 0d a6 3f 7f 01 	lea    r9,[rip+0x17f3fa6]        # 0x1829cb470
   1811d74ca:	ba 01 00 00 00       	mov    edx,0x1
   1811d74cf:	b9 58 06 00 00       	mov    ecx,0x658
   1811d74d4:	44 8d 42 13          	lea    r8d,[rdx+0x13]
   1811d74d8:	ff 15 2a 88 54 02    	call   QWORD PTR [rip+0x254882a]        # 0x18371fd08
   1811d74de:	48 89 84 24 58 01 00 	mov    QWORD PTR [rsp+0x158],rax
   1811d74e5:	00 
   1811d74e6:	48 85 c0             	test   rax,rax
   1811d74e9:	74 10                	je     0x1811d74fb
   1811d74eb:	49 8b d7             	mov    rdx,r15
   1811d74ee:	48 8b c8             	mov    rcx,rax
   1811d74f1:	e8 7a 59 27 00       	call   0x18144ce70
   1811d74f6:	48 8b f8             	mov    rdi,rax
   1811d74f9:	eb 03                	jmp    0x1811d74fe
   1811d74fb:	48 8b fe             	mov    rdi,rsi
   1811d74fe:	48 8b cf             	mov    rcx,rdi
   1811d7501:	e8 ba 5c 27 00       	call   0x18144d1c0
   1811d7506:	85 c0                	test   eax,eax
   1811d7508:	74 0f                	je     0x1811d7519
   1811d750a:	48 89 bc 24 58 01 00 	mov    QWORD PTR [rsp+0x158],rdi
   1811d7511:	00 
   1811d7512:	48 85 ff             	test   rdi,rdi
   1811d7515:	75 2e                	jne    0x1811d7545
   1811d7517:	eb 16                	jmp    0x1811d752f
   1811d7519:	48 85 ff             	test   rdi,rdi
   1811d751c:	74 11                	je     0x1811d752f
   1811d751e:	48 8b 07             	mov    rax,QWORD PTR [rdi]
   1811d7521:	ba 01 00 00 00       	mov    edx,0x1
   1811d7526:	48 8b cf             	mov    rcx,rdi
   1811d7529:	ff 10                	call   QWORD PTR [rax]
   1811d752b:	eb 02                	jmp    0x1811d752f
   1811d752d:	33 f6                	xor    esi,esi
   1811d752f:	41 8b d6             	mov    edx,r14d
   1811d7532:	49 8b cf             	mov    rcx,r15
   1811d7535:	e8 e6 d5 ff ff       	call   0x1811d4b20
   1811d753a:	48 8b f8             	mov    rdi,rax
   1811d753d:	48 89 84 24 58 01 00 	mov    QWORD PTR [rsp+0x158],rax
   1811d7544:	00 
   1811d7545:	89 74 24 30          	mov    DWORD PTR [rsp+0x30],esi
   1811d7549:	33 c9                	xor    ecx,ecx
   1811d754b:	e8 30 b1 f4 fe       	call   0x180122680
   1811d7550:	45 33 c0             	xor    r8d,r8d
   1811d7553:	33 d2                	xor    edx,edx
   1811d7555:	48 8d 4c 24 50       	lea    rcx,[rsp+0x50]
   1811d755a:	e8 91 1e f7 ff       	call   0x1811493f0
   1811d755f:	90                   	nop
   1811d7560:	48 8d 4c 24 70       	lea    rcx,[rsp+0x70]
   1811d7565:	e8 b6 d3 26 00       	call   0x181444920
   1811d756a:	90                   	nop
   1811d756b:	89 b4 24 48 01 00 00 	mov    DWORD PTR [rsp+0x148],esi
   1811d7572:	89 b4 24 80 00 00 00 	mov    DWORD PTR [rsp+0x80],esi
   1811d7579:	0f 57 c0             	xorps  xmm0,xmm0
   1811d757c:	f3 0f 7f 84 24 88 00 	movdqu XMMWORD PTR [rsp+0x88],xmm0
   1811d7583:	00 00 
   1811d7585:	89 b4 24 98 00 00 00 	mov    DWORD PTR [rsp+0x98],esi
   1811d758c:	48 89 74 24 38       	mov    QWORD PTR [rsp+0x38],rsi
   1811d7591:	89 74 24 40          	mov    DWORD PTR [rsp+0x40],esi
   1811d7595:	48 c7 44 24 44 01 00 	mov    QWORD PTR [rsp+0x44],0x1
   1811d759c:	00 00 
   1811d759e:	c7 84 24 a0 00 00 00 	mov    DWORD PTR [rsp+0xa0],0x1
   1811d75a5:	01 00 00 00 
   1811d75a9:	48 8d 44 24 50       	lea    rax,[rsp+0x50]
   1811d75ae:	48 89 84 24 a8 00 00 	mov    QWORD PTR [rsp+0xa8],rax
   1811d75b5:	00 
   1811d75b6:	e8 b5 1e fa ff       	call   0x181179470
   1811d75bb:	89 84 24 b0 00 00 00 	mov    DWORD PTR [rsp+0xb0],eax
   1811d75c2:	b9 01 00 00 00       	mov    ecx,0x1
   1811d75c7:	e8 74 1e fa ff       	call   0x181179440
   1811d75cc:	33 c9                	xor    ecx,ecx
   1811d75ce:	e8 ad 0f f8 ff       	call   0x181158580
   1811d75d3:	90                   	nop
   1811d75d4:	e8 87 cb f4 fe       	call   0x180124160
   1811d75d9:	e8 52 bc f4 fe       	call   0x180123230
   1811d75de:	48 8b 08             	mov    rcx,QWORD PTR [rax]
   1811d75e1:	48 89 4c 24 40       	mov    QWORD PTR [rsp+0x40],rcx
   1811d75e6:	c7 44 24 48 01 00 00 	mov    DWORD PTR [rsp+0x48],0x1
   1811d75ed:	00 
   1811d75ee:	e8 3d bc f4 fe       	call   0x180123230
   1811d75f3:	c7 00 01 00 00 00    	mov    DWORD PTR [rax],0x1
   1811d75f9:	48 8b cb             	mov    rcx,rbx
   1811d75fc:	e8 df c2 fa ff       	call   0x1811838e0
   1811d7601:	48 8b cb             	mov    rcx,rbx
   1811d7604:	e8 97 b8 fa ff       	call   0x181182ea0
   1811d7609:	48 8b d3             	mov    rdx,rbx
   1811d760c:	48 8b cf             	mov    rcx,rdi
   1811d760f:	e8 3c 05 00 00       	call   0x1811d7b50
   1811d7614:	89 44 24 30          	mov    DWORD PTR [rsp+0x30],eax
   1811d7618:	eb 4e                	jmp    0x1811d7668
   1811d761a:	8b 9c 24 c0 00 00 00 	mov    ebx,DWORD PTR [rsp+0xc0]
   1811d7621:	85 db                	test   ebx,ebx
   1811d7623:	74 39                	je     0x1811d765e
   1811d7625:	48 8d 4c 24 38       	lea    rcx,[rsp+0x38]
   1811d762a:	e8 11 96 f8 ff       	call   0x181160c40
   1811d762f:	4c 8b c0             	mov    r8,rax
   1811d7632:	8b d3                	mov    edx,ebx
   1811d7634:	48 8d 8c 24 e0 00 00 	lea    rcx,[rsp+0xe0]
   1811d763b:	00 
   1811d763c:	e8 af 1d f7 ff       	call   0x1811493f0
   1811d7641:	90                   	nop
   1811d7642:	48 8b d0             	mov    rdx,rax
   1811d7645:	48 8d 4c 24 50       	lea    rcx,[rsp+0x50]
   1811d764a:	e8 91 1f f7 ff       	call   0x1811495e0
   1811d764f:	90                   	nop
   1811d7650:	48 8d 8c 24 e0 00 00 	lea    rcx,[rsp+0xe0]
   1811d7657:	00 
   1811d7658:	e8 23 1e f7 ff       	call   0x181149480
   1811d765d:	90                   	nop
   1811d765e:	33 f6                	xor    esi,esi
   1811d7660:	48 8b bc 24 58 01 00 	mov    rdi,QWORD PTR [rsp+0x158]
   1811d7667:	00 
   1811d7668:	8b 9c 24 b0 00 00 00 	mov    ebx,DWORD PTR [rsp+0xb0]
   1811d766f:	85 db                	test   ebx,ebx
   1811d7671:	40 0f 94 c6          	sete   sil
   1811d7675:	44 8b c6             	mov    r8d,esi
   1811d7678:	33 d2                	xor    edx,edx
   1811d767a:	48 8d 4c 24 50       	lea    rcx,[rsp+0x50]
   1811d767f:	e8 cc 0f f8 ff       	call   0x181158650
   1811d7684:	8b cb                	mov    ecx,ebx
   1811d7686:	e8 b5 1d fa ff       	call   0x181179440
   1811d768b:	90                   	nop
   1811d768c:	e8 9f bb f4 fe       	call   0x180123230
   1811d7691:	48 8b 4c 24 40       	mov    rcx,QWORD PTR [rsp+0x40]
   1811d7696:	48 89 08             	mov    QWORD PTR [rax],rcx
   1811d7699:	e8 f2 ca f4 fe       	call   0x180124190
   1811d769e:	e8 bd cb f4 fe       	call   0x180124260
   1811d76a3:	85 c0                	test   eax,eax
   1811d76a5:	74 12                	je     0x1811d76b9
   1811d76a7:	48 8b 54 24 38       	mov    rdx,QWORD PTR [rsp+0x38]
   1811d76ac:	8b 8c 24 48 01 00 00 	mov    ecx,DWORD PTR [rsp+0x148]
   1811d76b3:	e8 a8 ba f4 fe       	call   0x180123160
   1811d76b8:	90                   	nop
   1811d76b9:	48 8b 8c 24 88 00 00 	mov    rcx,QWORD PTR [rsp+0x88]
   1811d76c0:	00 
   1811d76c1:	48 85 c9             	test   rcx,rcx
   1811d76c4:	74 05                	je     0x1811d76cb
   1811d76c6:	e8 65 ad f4 fe       	call   0x180122430
   1811d76cb:	45 33 c9             	xor    r9d,r9d
   1811d76ce:	45 33 c0             	xor    r8d,r8d
   1811d76d1:	48 8d 54 24 50       	lea    rdx,[rsp+0x50]
   1811d76d6:	48 8d 4c 24 70       	lea    rcx,[rsp+0x70]
   1811d76db:	e8 f0 d2 26 00       	call   0x1814449d0
   1811d76e0:	48 85 ff             	test   rdi,rdi
   1811d76e3:	74 0d                	je     0x1811d76f2
   1811d76e5:	48 8b 07             	mov    rax,QWORD PTR [rdi]
   1811d76e8:	ba 01 00 00 00       	mov    edx,0x1
   1811d76ed:	48 8b cf             	mov    rcx,rdi
   1811d76f0:	ff 10                	call   QWORD PTR [rax]
   1811d76f2:	48 8d 4c 24 50       	lea    rcx,[rsp+0x50]
   1811d76f7:	e8 44 4a f0 ff       	call   0x1810dc140
   1811d76fc:	90                   	nop
   1811d76fd:	48 8d 4c 24 70       	lea    rcx,[rsp+0x70]
   1811d7702:	e8 69 d2 26 00       	call   0x181444970
   1811d7707:	90                   	nop
   1811d7708:	48 8d 4c 24 50       	lea    rcx,[rsp+0x50]
   1811d770d:	e8 6e 1d f7 ff       	call   0x181149480
   1811d7712:	8b 44 24 30          	mov    eax,DWORD PTR [rsp+0x30]
   1811d7716:	4c 8d 9c 24 20 01 00 	lea    r11,[rsp+0x120]
   1811d771d:	00 
   1811d771e:	49 8b 5b 20          	mov    rbx,QWORD PTR [r11+0x20]
   1811d7722:	49 8b 73 30          	mov    rsi,QWORD PTR [r11+0x30]
   1811d7726:	49 8b e3             	mov    rsp,r11
   1811d7729:	41 5f                	pop    r15
   1811d772b:	41 5e                	pop    r14
   1811d772d:	5f                   	pop    rdi
   1811d772e:	c3                   	ret
