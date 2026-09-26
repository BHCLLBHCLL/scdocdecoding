# SpaceClaim V19 (2019 R3) feature inventory for scdm_cases

Generated 2026-09-26T01:40:00+08:00 from SpaceClaim.Api.V19.Scripting.dll reflection (154 command classes), Snippets\V19 and the scdocdecoding repo docs. Machine-readable: `feature_inventory.json`, `combo_plan.json`; raw reflection dump in `raw/`.

## Totals

- Features: **82**; single-case variants: **190**; combo cases: **32**
- Priority (features / variants): P0 32 / 88, P1 28 / 65, P2 22 / 37
- Repo support: supported 28, partial 30, none 24
- Headless feasibility: yes 41, needs selection setup 37, GUI-only 1, other/unknown 3

## Per category

| Category | Features | Variants | P0 | P1 | P2 |
|---|---|---|---|---|---|
| `00_smoke` | 1 | 1 | 1 | 0 | 0 |
| `01_primitives` | 7 | 17 | 5 | 2 | 0 |
| `02_sketch` | 11 | 28 | 4 | 5 | 2 |
| `03_pull` | 9 | 24 | 5 | 3 | 1 |
| `04_edge` | 4 | 9 | 2 | 0 | 2 |
| `05_boolean` | 5 | 12 | 4 | 1 | 0 |
| `06_move_pattern` | 8 | 15 | 3 | 2 | 3 |
| `07_shell_offset` | 5 | 11 | 1 | 3 | 1 |
| `08_sheetmetal` | 1 | 3 | 0 | 1 | 0 |
| `09_beam` | 2 | 6 | 0 | 2 | 0 |
| `10_assembly` | 5 | 12 | 3 | 0 | 2 |
| `11_doc_attrs` | 12 | 24 | 4 | 3 | 5 |
| `12_repair_prepare` | 5 | 11 | 0 | 2 | 3 |
| `13_surface_curve` | 5 | 10 | 0 | 3 | 2 |
| `14_holes_threads` | 1 | 4 | 0 | 1 | 0 |
| `15_mesh_facet` | 1 | 3 | 0 | 0 | 1 |
| `20_combo` | - | 32 | 15 | 14 | 3 |

## 00_smoke — Smoke / pipeline checks

| id | Feature (EN / 中文) | V19 API | Variants | Impact | Repo | Prio | Headless |
|---|---|---|---|---|---|---|---|
| `smoke_box` | Block (smoke) / 方块（冒烟） | `BlockBody.Create` | 00_smoke_box_001_20x20x20 | geometry-only (SAB) | supported | P0 | yes |

## 01_primitives — Primitive solids (block, cylinder, sphere, tube, cone/torus via revolve)

| id | Feature (EN / 中文) | V19 API | Variants | Impact | Repo | Prio | Headless |
|---|---|---|---|---|---|---|---|
| `prim_block` | Block / 方块 | `BlockBody.Create(Point,Point,ExtrudeType)` | 01_primitives_block_001_10x20x30<br>01_primitives_block_002_offset_neg<br>01_primitives_block_003_thin_100x100x0p5 | geometry-only (SAB) | supported | P0 | yes |
| `prim_cylinder` | Cylinder / 圆柱 | `CylinderBody.Create(center,start,end,ExtrudeType)` | 01_primitives_cylinder_001_r10_h20_z<br>01_primitives_cylinder_002_r5_h50_x<br>01_primitives_cylinder_003_r2_h1_oblique | geometry-only (SAB) | supported | P0 | yes |
| `prim_sphere` | Sphere / 球 | `SphereBody.Create(center,endPoint,ExtrudeType)` | 01_primitives_sphere_001_r10<br>01_primitives_sphere_002_r3_offcenter | geometry-only (SAB) | supported | P0 | yes |
| `prim_tube` | Tube around curve / 管道 | `TubeBody.Create(ISelection curve, radius, ExtrudeType)` | 01_primitives_tube_001_line_r2_l50<br>01_primitives_tube_002_arc_r3<br>01_primitives_tube_003_spline_r1 | geometry-only (SAB) | partial | P1 | needs selection setup (create DesignCurve first) |
| `prim_cone_revolve` | Cone / frustum (revolve of triangle/trapezoid) / 圆锥/圆台 | `SketchLine.CreateChain`<br>`RevolveFaces.Execute(face, Line axis, angle, RevolveFaceOptions)` | 01_primitives_cone_001_r10_h20<br>01_primitives_cone_002_frustum_r10_r5_h15 | geometry-only (SAB) | supported | P0 | needs selection setup (sketch->solidify->face) |
| `prim_torus_revolve` | Torus (revolve of circle) / 圆环 | `SketchCircle.Create`<br>`RevolveFaces.Execute` | 01_primitives_torus_001_R20_r5<br>01_primitives_torus_002_partial_180deg | geometry-only (SAB) | supported | P0 | needs selection setup |
| `prim_planar_body` | Planar (sheet) body from curves / 平面体 | `PlanarBody.Create(Plane, curves, parent, name)` | 01_primitives_planar_001_rect_40x20<br>01_primitives_planar_002_circle_r15 | geometry-only (SAB) | partial | P1 | yes |

## 02_sketch — Sketch curves, sketch constraints & dimensions (DesignCurve / SketchCurveDef)

| id | Feature (EN / 中文) | V19 API | Variants | Impact | Repo | Prio | Headless |
|---|---|---|---|---|---|---|---|
| `sk_line` | Sketch line / polyline / 直线 | `SketchLine.Create`<br>`SketchLine.CreateChain` | 02_sketch_line_001_single_50<br>02_sketch_line_002_chain_closed_tri<br>02_sketch_line_003_construction | document.xml only (no new geometry) (SketchCurveDef in PartSketchCurveContainerDef (document.xml) + wire geometry) | partial | P0 | yes (ViewHelper.SetSketchPlane + create; leave in sketch mode or SetViewMode(Solid) to solidify) |
| `sk_rect` | Sketch rectangle / 矩形 | `SketchRectangle.Create(p1,p2,p3)` | 02_sketch_rect_001_40x20<br>02_sketch_rect_002_rotated_30deg | document.xml only (no new geometry) (4 line SketchCurveDef) | partial | P1 | yes |
| `sk_circle` | Sketch circle / 圆 | `SketchCircle.Create(Point2D,radius)` | 02_sketch_circle_001_r10<br>02_sketch_circle_002_two_concentric_r5_r10 | document.xml only (no new geometry) (circle SketchCurveDef) | partial | P0 | yes |
| `sk_arc` | Sketch arc (center/3-point/tangent/sweep) / 圆弧 | `SketchArc.Create`<br>`SketchArc.Create3PointArc`<br>`SketchArc.CreateSweepArc`<br>`SketchArc.CreateTangentArc` | 02_sketch_arc_001_center_r20_90deg<br>02_sketch_arc_002_3point<br>02_sketch_arc_003_tangent_after_line | document.xml only (no new geometry) (arc SketchCurveDef with interval) | partial | P0 | yes |
| `sk_ellipse` | Sketch ellipse / 椭圆 | `SketchEllipse.Create` | 02_sketch_ellipse_001_a20_b10<br>02_sketch_ellipse_002_rotated_45 | document.xml only (no new geometry) | partial | P1 | yes |
| `sk_polygon` | Sketch polygon / 多边形 | `SketchPolygon.Create(Point2D,dirX,dirY,internalRadius,n)` | 02_sketch_polygon_001_hex_r10<br>02_sketch_polygon_002_pent_r8 | document.xml only (no new geometry) | partial | P2 | yes |
| `sk_spline` | Sketch spline (NURBS through points) / 样条 | `SketchNurbs.CreateFrom2DPoints(periodic, points)` | 02_sketch_spline_001_open_5pts<br>02_sketch_spline_002_periodic_6pts<br>02_sketch_spline_003_end_tangents | document.xml only (no new geometry) (NurbsCurve serialized in document.xml) | none | P0 | yes |
| `sk_point_offset` | Sketch point / offset curve / corner / 2D round / trim / split / 点/偏移/倒角/修剪 | `SketchPoint.Create`<br>`SketchOffsetCurve.Create`<br>`SketchCorner.Create`<br>`Sketch2DRound.Create`<br>`TrimSketchCurve.Execute`<br>`SplitSketchCurve.Execute` | 02_sketch_point_001<br>02_sketch_offset_001_rect_offset3<br>02_sketch_round2d_001_rect_corner_r4 | document.xml only (no new geometry) | partial | P2 | needs selection setup |
| `sk_constraints` | Sketch constraints (horizontal, vertical, coincident, tangent, parallel, perpendicular, concentric, equal, midpoint, symmetric, fixed) / 草图约束 | `Constraint.Create*`<br>`SketchHelper.StartConstraintSketching`<br>`ConstraintHelper.ModelWellDefined` | 02_sketch_constraint_001_hv_rect<br>02_sketch_constraint_002_tangent_line_arc<br>02_sketch_constraint_003_concentric_equal | document.xml only (no new geometry) (constraint objects in sketch) | none | P1 | needs selection setup (SelectionPoint on curves); may require constraint sketching mode - verify headless |
| `sk_dimensions` | Sketch dimensions (length/radial/diameter/angle/distance) / 尺寸 | `Dimension.CreateLength`<br>`Dimension.CreateRadial`<br>`Dimension.CreateDiameter`<br>`Dimension.CreateAngle`<br>`Dimension.CreateDistance`<br>`Dimension.Modify` | 02_sketch_dim_001_length_40<br>02_sketch_dim_002_radius_10<br>02_sketch_dim_003_angle_30 | document.xml only (no new geometry) | none | P1 | needs selection setup; verify headless |
| `sk_datum_curve` | 3D design curve (line/arc/spline outside sketch) / 3D曲线 | `DesignCurve.Create (API)`<br>`SketchCurve.Create`<br>`ProjectToSketch.Create` | 02_sketch_designcurve_001_3d_line<br>02_sketch_designcurve_002_helix_spline | geometry (SAB) + document.xml tree entries | partial | P1 | yes |

## 03_pull — Pull-family solid creation: extrude, cut, revolve, sweep, loft, helix

| id | Feature (EN / 中文) | V19 API | Variants | Impact | Repo | Prio | Headless |
|---|---|---|---|---|---|---|---|
| `pull_extrude_face` | Extrude (pull) sketch region to solid / 拉动-拉伸 | `ExtrudeFaces.Execute(sel, Direction, distance, ExtrudeFaceOptions)` | 03_pull_extrude_001_rect_40x20_h10<br>03_pull_extrude_002_circle_r10_h25<br>03_pull_extrude_003_spline_profile_h5<br>03_pull_extrude_004_symmetric_h20 | geometry-only (SAB) | supported | P0 | needs selection setup (face from solidified sketch) |
| `pull_extrude_cut` | Extrude cut (pocket / through hole) / 拉动-切除 | `ExtrudeFaces.Execute ExtrudeType.Cut`<br>`ExtrudeFaces.UpTo` | 03_pull_cut_001_pocket_rect_depth5<br>03_pull_cut_002_through_hole_r4<br>03_pull_cut_003_upto_face | geometry-only (SAB) | supported | P0 | needs selection setup |
| `pull_face_offset` | Pull existing face (grow/shrink body) / 拉动面 | `ExtrudeFaces.Execute on body face` | 03_pull_face_001_block_top_plus10<br>03_pull_face_002_block_side_minus3 | geometry-only (SAB) | supported | P1 | needs selection setup (pick face by normal) |
| `pull_extrude_edges` | Extrude edges/curves to surface / 拉伸边 | `ExtrudeEdges.Execute` | 03_pull_extrudeedge_001_line_to_sheet<br>03_pull_extrudeedge_002_arc_to_sheet | geometry-only (SAB) | partial | P1 | needs selection setup |
| `pull_revolve` | Revolve / 旋转 | `RevolveFaces.Execute(sel, Line axis, angle, RevolveFaceOptions)`<br>`RevolveEdges.Execute` | 03_pull_revolve_001_rect_360<br>03_pull_revolve_002_rect_90<br>03_pull_revolve_003_spline_profile_360 | geometry-only (SAB) | supported | P0 | needs selection setup |
| `pull_helix` | Revolve by helix (spring/thread) / 螺旋 | `RevolveFaces.ByHelix`<br>`RevolveEdges.ByHelix` | 03_pull_helix_001_circle_r1_pitch5_h20<br>03_pull_helix_002_tapered_5deg | geometry-only (SAB) | partial | P1 | needs selection setup |
| `pull_sweep` | Sweep profile along trajectory / 扫掠 | `Sweep.Execute(sel, trajectories, SweepCommandOptions)` | 03_pull_sweep_001_circle_along_arc<br>03_pull_sweep_002_rect_along_spline<br>03_pull_sweep_003_along_polyline | geometry-only (SAB) | partial | P0 | needs selection setup (profile face + trajectory curve) |
| `pull_loft` | Loft / blend between profiles / 放样/混合 | `Loft.Create(blendSelection, guideSelection, LoftOptions)`<br>`Loft.CreateCenterLine` | 03_pull_loft_001_rect_to_circle<br>03_pull_loft_002_three_circles<br>03_pull_loft_003_ruled | geometry-only (SAB) | partial | P0 | needs selection setup |
| `pull_extrude_profile` | Extrude API Profile directly / 轮廓拉伸 | `ExtrudeProfile.Execute(Profile, distance, parent, name)` | 03_pull_profile_001_rect_30x10_h5<br>03_pull_profile_002_circle_r6_h12 | geometry-only (SAB) | supported | P2 | yes (no selection needed; also allows body naming) |

## 04_edge — Edge treatments: constant round, full round, chamfer

| id | Feature (EN / 中文) | V19 API | Variants | Impact | Repo | Prio | Headless |
|---|---|---|---|---|---|---|---|
| `edge_round` | Constant radius round (fillet) / 倒圆角 | `ConstantRound.Execute(sel edges, radius, ConstantRoundOptions)` | 04_edge_round_001_block_1edge_r3<br>04_edge_round_002_block_all12_r2<br>04_edge_round_003_cyl_top_r2<br>04_edge_round_004_vertex_blend_3edges_r4 | geometry-only (SAB) (+ RoundInfo/round face attributes in document.xml) | partial | P0 | needs selection setup (edges by geometry) |
| `edge_full_round` | Full round / 全圆角 | `FullRound.Execute(selFaces)` | 04_edge_fullround_001_rib_3faces | geometry-only (SAB) | partial | P2 | needs selection setup |
| `edge_chamfer` | Chamfer (equal/unequal) / 倒角 | `Chamfer.Execute(sel, distance)`<br>`Chamfer.Execute(sel, d1, d2)` | 04_edge_chamfer_001_block_1edge_d2<br>04_edge_chamfer_002_block_4edges_d1_d3<br>04_edge_chamfer_003_cyl_top_d1 | geometry-only (SAB) | supported | P0 | needs selection setup |
| `edge_split_round` | Round utilities (split round, restore rounds) / 圆角工具 | `SplitRound.Execute`<br>`NamedSelection.RestoreRounds`<br>`RoundInfo.Create` | 04_edge_splitround_001 | geometry (SAB) + document.xml tree entries | none | P2 | needs selection setup |

## 05_boolean — Combine/split: merge, subtract, intersect, split body/face

| id | Feature (EN / 中文) | V19 API | Variants | Impact | Repo | Prio | Headless |
|---|---|---|---|---|---|---|---|
| `bool_merge` | Combine - merge (union) / 组合-合并 | `Combine.Merge(target, tool)`<br>`MergeBodies.Execute` | 05_boolean_merge_001_two_blocks_overlap<br>05_boolean_merge_002_block_plus_cyl<br>05_boolean_merge_003_touching_faces | geometry-only (SAB) | supported | P0 | yes (bodies from GetRootPart().Bodies) |
| `bool_subtract` | Combine - subtract (cut body with tool, RemoveRegions) / 组合-减 | `Combine.Intersect(target, tool, MakeSolidsOptions)`<br>`Combine.RemoveRegions` | 05_boolean_subtract_001_block_minus_cyl<br>05_boolean_subtract_002_block_minus_sphere<br>05_boolean_subtract_003_keep_cutter | geometry-only (SAB) | supported | P0 | yes (verify region-selection step for subtract; SpaceClaim subtract = Intersect + RemoveRegions) |
| `bool_intersect` | Combine - intersect (common) / 组合-相交 | `Combine.Intersect + RemoveRegions` | 05_boolean_intersect_001_block_sphere<br>05_boolean_intersect_002_two_cylinders_cross | geometry-only (SAB) | partial | P0 | yes |
| `bool_split_body` | Split body by plane / face / body / 拆分主体 | `SplitBody.ByCutter(body, Plane)`<br>`SplitBody.ByCutter(body, toolFaces, extend)` | 05_boolean_splitbody_001_block_by_plane_mid<br>05_boolean_splitbody_002_cyl_by_oblique_plane<br>05_boolean_splitbody_003_by_face | geometry-only (SAB) | supported | P0 | yes |
| `bool_imprint` | Imprint / intersect to curves / 压印 | `Combine.Intersect(target, tool, MakeCurvesOptions)`<br>`FixImprint` | 05_boolean_imprint_001_block_cyl_curves | geometry-only (SAB) | partial | P1 | yes |

## 06_move_pattern — Move/rotate/scale/mirror/pattern

| id | Feature (EN / 中文) | V19 API | Variants | Impact | Repo | Prio | Headless |
|---|---|---|---|---|---|---|---|
| `mp_translate` | Move - translate / 移动-平移 | `Move.Translate(sel, Direction, distance, MoveOptions)` | 06_move_translate_001_block_x25<br>06_move_translate_002_copy_y30 | geometry-only (SAB) | supported | P1 | yes |
| `mp_rotate` | Move - rotate / 移动-旋转 | `Move.Rotate(sel, Line axis, angle, MoveOptions)` | 06_move_rotate_001_block_z45<br>06_move_rotate_002_cyl_x90_copy | geometry-only (SAB) | supported | P1 | yes |
| `mp_scale` | Scale body (uniform / non-uniform) / 缩放 | `Scale.Execute(sel, origin, scale)`<br>`Scale.Execute(sel, frame, Vector scale)` | 06_move_scale_001_uniform_2x<br>06_move_scale_002_nonuniform_1x2x0p5 | geometry-only (SAB) | supported | P2 | yes |
| `mp_mirror` | Mirror body (and mirror relationship) / 镜像 | `Mirror.Execute(sel, mirrorPlane, MirrorOptions)`<br>`DatumPlaneCreator.Create` | 06_move_mirror_001_block_about_yz<br>06_move_mirror_002_merge_halves | geometry (SAB) + document.xml tree entries (mirror plane datum; possible MirrorRelation) | partial | P0 | needs selection setup (datum plane or face as mirror plane) |
| `mp_pattern_linear` | Linear pattern / 线性阵列 | `Pattern.CreateLinear(sel, LinearPatternData)`<br>`Pattern.ModifyLinear` | 06_pattern_linear_001_cyl_1d_5x10<br>06_pattern_linear_002_hole_2d_3x4<br>06_pattern_linear_003_body_copy_3 | geometry (SAB) + document.xml tree entries (PatternDef/pattern relationship entries) | none | P0 | needs selection setup (face group or body) |
| `mp_pattern_circular` | Circular pattern / 圆形阵列 | `Pattern.CreateCircular(sel, CircularPatternData)` | 06_pattern_circular_001_holes_6_360<br>06_pattern_circular_002_bodies_4_180 | geometry (SAB) + document.xml tree entries | none | P0 | needs selection setup |
| `mp_pattern_fill` | Fill pattern / 填充阵列 | `Pattern.CreateFill(sel, FillPatternData)` | 06_pattern_fill_001_holes_in_plate | geometry (SAB) + document.xml tree entries | none | P2 | needs selection setup |
| `mp_along_trajectory` | Move along trajectory / orient / 沿轨迹移动 | `Move.AlongTrajectory`<br>`Move.OrientTo`<br>`Move.ToCoordinate` | 06_move_trajectory_001_block_along_arc | geometry-only (SAB) | supported | P2 | needs selection setup |

## 07_shell_offset — Shell, offset, thicken, draft, replace/detach faces

| id | Feature (EN / 中文) | V19 API | Variants | Impact | Repo | Prio | Headless |
|---|---|---|---|---|---|---|---|
| `so_shell` | Shell (remove faces / hollow) / 抽壳 | `Shell.RemoveFaces(sel faces, thickness)`<br>`Shell.ShellBodies(sel bodies, thickness)` | 07_shell_open_001_block_top_t2<br>07_shell_closed_002_hollow_sphere_t1<br>07_shell_open_003_cyl_top_t1p5 | geometry-only (SAB) | supported | P0 | needs selection setup |
| `so_offset` | Offset faces / 偏移面 | `OffsetFaces.Execute(sel, offset, OffsetFaceOptions)`<br>`OffsetRelation.ChangeOffset` | 07_offset_001_block_top_plus3<br>07_offset_002_cyl_face_minus1 | geometry (SAB) + document.xml tree entries (possible OffsetRelation) | partial | P1 | needs selection setup |
| `so_thicken` | Thicken surface to solid / 加厚 | `ThickenFaces.Execute(sel, Direction, value, ThickenFaceOptions)` | 07_thicken_001_planar_t2<br>07_thicken_002_cyl_sheet_t1 | geometry-only (SAB) | supported | P1 | needs selection setup |
| `so_draft` | Draft faces / 拔模 | `DraftFaces.Execute(sel, refFaces, DraftSide, angle, ExtrudeType, DraftOptions)` | 07_draft_001_block_4sides_5deg<br>07_draft_002_cyl_side_3deg | geometry-only (SAB) | supported | P1 | needs selection setup |
| `so_replace_detach` | Replace faces / detach faces / 替换面/分离面 | `ReplaceFacesWithFace.Execute`<br>`DetachFaces.Execute` | 07_replaceface_001_block_top_to_plane<br>07_detach_001_block_top | geometry-only (SAB) | supported | P2 | needs selection setup |

## 08_sheetmetal — Sheet metal (no V19 scripting command -> GUI/API only)

| id | Feature (EN / 中文) | V19 API | Variants | Impact | Repo | Prio | Headless |
|---|---|---|---|---|---|---|---|
| `sm_all` | Sheet metal (convert, flange, bend, unfold, junction, relief) / 钣金 | `NONE in SpaceClaim.Api.V19.Scripting; raw API SheetMetalAspect/Bend are read-only (no Create)` | 08_sheetmetal_convert_001_block_t2<br>08_sheetmetal_flange_001_90deg_l20<br>08_sheetmetal_unfold_001 | geometry (SAB) + document.xml tree entries (sheet metal part attributes, bends) | none | P1 | GUI-only (user builds in GUI once with recording on; saves into 08_sheetmetal) |

## 09_beam — Beams & beam profiles

| id | Feature (EN / 中文) | V19 API | Variants | Impact | Repo | Prio | Headless |
|---|---|---|---|---|---|---|---|
| `beam_profile` | Beam profile creation (I/L/T/channel/rect/circular/...) / 梁截面 | `BeamProfile.CreateI/CreateL/CreateT/CreateChannel/CreateRectangular/CreateCircular/CreateDisk/CreateFlatBar/CreateHat/CreateZ/CreateCustom`<br>`BeamProfile.CreateFromLibrary` | 09_beam_profile_001_I_100x50<br>09_beam_profile_002_rect_tube_60x40x3<br>09_beam_profile_003_circular_d40_d34 | geometry (SAB) + document.xml tree entries (profile component + beam section properties) | none | P1 | yes |
| `beam_create` | Beam along curve / 创建梁 | `Beam.Create(sel curves, profile)`<br>`Beam.SetOrientation/SetPosition/SetType/ReverseBeam`<br>`Beam.ExtractProfile` | 09_beam_create_001_line_I<br>09_beam_create_002_frame_4lines_rect<br>09_beam_create_003_orient30_centroid | geometry (SAB) + document.xml tree entries | none | P1 | needs selection setup (DesignCurve + profile) |

## 10_assembly — Components, instances, mirror components, assembly conditions

| id | Feature (EN / 中文) | V19 API | Variants | Impact | Repo | Prio | Headless |
|---|---|---|---|---|---|---|---|
| `asm_component` | Create component / move bodies to component / 组件 | `ComponentHelper.CreateAtRoot`<br>`ComponentHelper.MoveBodiesToComponent`<br>`ComponentHelper.CreateSeparateComponents`<br>`ComponentHelper.SetName` | 10_assembly_component_001_two_bodies_two_comps<br>10_assembly_component_002_nested_2levels<br>10_assembly_component_003_separate_components_4 | geometry (SAB) + document.xml tree entries (ComponentDef/PartDef, per-part SAB, moniker rels) | partial | P0 | yes |
| `asm_instance` | Component instances (copy/paste component, transform) / 组件实例 | `Copy.ToClipboard/Paste.FromClipboard`<br>`ComponentHelper.CopyToComponent`<br>`Move.Translate on component`<br>`ComponentHelper.MakeIndependent` | 10_assembly_instance_001_3_instances_translated<br>10_assembly_instance_002_rotated_instance<br>10_assembly_instance_003_make_independent | geometry (SAB) + document.xml tree entries (instances share one PartDef; <trans> matrix) | partial | P0 | yes (clipboard in headless: verify) |
| `asm_mirror_components` | Mirror components / 镜像组件 | `MirrorComponents.Execute` | 10_assembly_mirrorcomp_001 | geometry (SAB) + document.xml tree entries | none | P2 | needs selection setup |
| `asm_conditions` | Assembly conditions (align, tangent, orient, anchor, rigid, gear) / 装配约束 | `(raw API) AlignCondition.Create / TangentCondition.Create / OrientCondition.Create / AnchorCondition.Create / RigidCondition.Create / GearCondition.Create (SpaceClaim.Api.V19)` | 10_assembly_align_001_axis_axis<br>10_assembly_tangent_001_face_face<br>10_assembly_anchor_001_plate<br>10_assembly_rigid_001 | geometry (SAB) + document.xml tree entries (condition entries) | none | P0 | needs selection setup (raw API on component faces/axes; verify signatures in API_Class_Library.chm) |
| `asm_insert_file` | Insert external file as component / 插入文件 | `DocumentInsert.Execute(filename)` | 10_assembly_insert_001_step_block | geometry (SAB) + document.xml tree entries (external reference / import source) | partial | P2 | yes |

## 11_doc_attrs — Document attributes: names, layers, colors, named selections, datums, views, units

| id | Feature (EN / 中文) | V19 API | Variants | Impact | Repo | Prio | Headless |
|---|---|---|---|---|---|---|---|
| `doc_rename` | Rename body/component (captions) / 重命名 | `RenameObject.Execute(sel, name)`<br>`HasNameExtensions.SetName` | 11_doc_rename_001_body_Block_A<br>11_doc_rename_002_unicode_name | document.xml only (no new geometry) (CaptionDef) | supported | P0 | yes |
| `doc_layers` | Layers (create, assign, color, visibility, lock) / 图层 | `Layers.Create/AssignLayer/SetColor/SetVisibility/SetLock/Rename` | 11_doc_layers_001_two_layers_assign<br>11_doc_layers_002_hidden_locked | document.xml only (no new geometry) (LayerDef) | supported | P0 | yes |
| `doc_colors` | Body / face color, fill style / 颜色 | `ColorHelper.SetColor(sel, SetColorOptions, Color)`<br>`ColorHelper.SetFillStyle` | 11_doc_color_001_body_red<br>11_doc_color_002_face_green<br>11_doc_color_003_transparent_50 | geometry (SAB) + document.xml tree entries (NominalBodyDef color; SAB rgb_color attrib) | partial | P0 | yes |
| `doc_named_selection` | Named selections (groups) / 命名选择/组 | `NamedSelection.Create(primary, secondary)`<br>`NamedSelection.Rename/Replace/Delete` | 11_doc_ns_001_faces_top_bottom<br>11_doc_ns_002_edges_and_body<br>11_doc_ns_003_renamed | document.xml only (no new geometry) (NamedSelectionDef/StoredSelectionTableDef + monikers) | partial | P0 | yes |
| `doc_datum` | Datum plane / axis / point / origin (coordinate system) / 基准面/轴/点/坐标系 | `DatumPlaneCreator.Create`<br>`DatumLineCreator.Create`<br>`DatumPointCreator.Create`<br>`DatumOriginCreator.Create` | 11_doc_datum_001_plane_offset_z10<br>11_doc_datum_002_axis_and_point<br>11_doc_datum_003_origin_rotated | document.xml only (no new geometry) (DatumPlaneDef/DatumLineDef/DatumPointDef/CoordinateSystemDef) | none | P1 | yes |
| `doc_named_view` | Named views / section plane / 命名视图 | `ViewHelper.CreateNamedView`<br>`ViewHelper.SetProjection`<br>`ViewHelper.SetSectionPlane` | 11_doc_view_001_named_iso<br>11_doc_view_002_two_views | document.xml only (no new geometry) (SavedViewsDef / windows.xml) | none | P1 | needs GUI window? (headless has no view) - test both modes |
| `doc_coordsys` | Coordinate system / 坐标系 | `(raw API) CoordinateSystem.Create`<br>`DatumOriginCreator.Create` | 11_doc_coordsys_001_translated_rotated | document.xml only (no new geometry) | none | P2 | yes |
| `doc_notes` | 3D notes / annotations / 注释 | `(raw API) Note.Create` | 11_doc_note_001_text_on_face | document.xml only (no new geometry) (annotation plane + note) | none | P2 | needs selection setup (raw API, verify) |
| `doc_drawing_sheet` | Drawing sheet with general/projected views / 工程图纸 | `(raw API) DrawingSheet.Create`<br>`DrawingView.CreateGeneralView/CreateProjectedView` | 11_doc_drawing_001_A3_3views | document.xml only (no new geometry) (DrawingSheetDef, views) | none | P2 | unknown (drawing windows in headless - verify) |
| `doc_visibility` | Visibility / suppress for physics / lock / 可见性/抑制/锁定 | `ViewHelper.SetObjectVisibility`<br>`ViewHelper.SetSuppressForPhysics`<br>`ViewHelper.LockBodies` | 11_doc_visibility_001_hidden_body<br>11_doc_suppress_001<br>11_doc_lock_001 | document.xml only (no new geometry) | none | P2 | yes |
| `doc_material` | Material assignment / 材料 | `(raw API) DocumentMaterial.Create / LibraryMaterial -> DesignBody.Material` | 11_doc_material_001_steel | document.xml only (no new geometry) (DocumentMaterial / MaterialLibrary) | none | P2 | yes (raw API, verify) |
| `doc_units` | Document units (mm / m / inch) / 单位 | `(raw API) Units / Document units setter (to locate); UnitsHelper.GetDocumentUnits is read-only` | 11_doc_units_001_inch<br>11_doc_units_002_meter | document.xml only (no new geometry) (DocumentUnitsDef) | supported | P1 | unknown - no scripting setter found; may need API/GUI |

## 12_repair_prepare — NEW: Repair (Fix*) and Prepare (midsurface, share topology, volume extract, enclosure...)

| id | Feature (EN / 中文) | V19 API | Variants | Impact | Repo | Prio | Headless |
|---|---|---|---|---|---|---|---|
| `rp_fix` | Repair: stitch, gaps, missing faces, split edges, extra edges, small faces, short edges, duplicates, merge faces / 修复 | `StitchFaces/FixGaps/FixMissingFaces/FixSplitEdges/FixExtraEdges/FixSmallFaces/FixShortEdges/FixDuplicateFaces/FixCurveGaps/FixDuplicateCurves/FixExtendableSurfaces/FixInterference .FindAndFix` | 12_repair_stitch_001_six_sheets_to_solid<br>12_repair_missingface_001_open_box<br>12_repair_extraedges_001_split_face_merge | geometry-only (SAB) | supported | P2 | yes (need crafted defective inputs) |
| `rp_midsurface` | Midsurface / 中面 | `Midsurface.Convert(bodies, thickness)`<br>`MidsurfaceOffsetFaces.Create`<br>`MidsurfaceAspectExtensions.SetThickness` | 12_prepare_midsurface_001_plate_t2<br>12_prepare_midsurface_002_L_bracket_t3 | geometry (SAB) + document.xml tree entries (sheet body + MidSurfaceAspect thickness) | none | P1 | yes |
| `rp_share_topology` | Share topology / 共享拓扑 | `ShareTopology.FindAndFix`<br>`ForceShareTopology.Execute`<br>`UnShareTopology.Execute`<br>`SharePrep.Execute` | 12_prepare_sharetopo_001_two_blocks_touching<br>12_prepare_sharetopo_002_force_tol0p1 | geometry (SAB) + document.xml tree entries | none | P1 | yes |
| `rp_volume_extract` | Volume extract / enclosure / workpiece / shrinkwrap / 体积抽取/包围 | `VolumeExtract.Create`<br>`Enclosure.Create`<br>`Workpiece.Create`<br>`Shrinkwrap.Create` | 12_prepare_enclosure_001_box_cushion10<br>12_prepare_volumeextract_001_pipe<br>12_prepare_workpiece_001 | geometry (SAB) + document.xml tree entries (EnclosureAspect/VolumeExtractionAspect) | none | P2 | needs selection setup |
| `rp_icepak` | Icepak objects (enclosure, fan, grille, opening, simplify) / Icepak 对象 | `IcepakEnclosure/IcepakFan/IcepakGrille/IcepakOpening/IcepakSimplify` | 12_prepare_icepak_simplify_001_level1 | geometry (SAB) + document.xml tree entries | none | P2 | yes (niche) |

## 13_surface_curve — NEW: Surface/sheet bodies, fill/patch, project/wrap, split face, 3D curves

| id | Feature (EN / 中文) | V19 API | Variants | Impact | Repo | Prio | Headless |
|---|---|---|---|---|---|---|---|
| `sc_surfaces` | Surface bodies: circular/rectangular surface, SurfaceBody from API surface / 曲面体 | `CircularSurface.Create`<br>`RectangularSurface.Create`<br>`SurfaceBody.Create(Surface, BoxUV)` | 13_surface_circular_001_r20<br>13_surface_rect_001_30x10<br>13_surface_body_001_cylinder_patch | geometry-only (SAB) | partial | P1 | yes |
| `sc_fill` | Fill / patch (cap holes, N-sided patch) / 填充 | `Fill.Execute(sel, secondary, FillOptions, FillMode)` | 13_fill_001_cap_open_box<br>13_fill_002_patch_4_splines | geometry-only (SAB) | partial | P1 | needs selection setup |
| `sc_split_face` | Split face (by curves/cutter/two points/parametric), split edge / 拆分面/边 | `SplitFace.ByTwoPoints/ByCutter/ByParametric/ByCurves`<br>`SplitEdge.ByCount/ByLength/ByProportion` | 13_splitface_001_block_top_two_points<br>13_splitedge_001_by_count3 | geometry-only (SAB) | supported | P1 | needs selection setup |
| `sc_project_wrap` | Project curves to solid / wrap / imprint / 投影/缠绕 | `ProjectToSolid.Execute`<br>`Wrap.Create`<br>`ProjectToSketch.Create`<br>`MoveImprintEdges.Execute` | 13_project_001_circle_onto_block_top<br>13_wrap_001_rect_onto_cylinder | geometry-only (SAB) | partial | P2 | needs selection setup |
| `sc_convert_solid` | Convert to solid / auto-skin / skin from height field / 转换为实体 | `ConvertToSolid.Execute`<br>`AutoSkin.Execute` | 13_convertsolid_001_closed_sheets | geometry-only (SAB) | partial | P2 | yes |

## 14_holes_threads — NEW: Standard holes (counterbore/countersink/tapped)

| id | Feature (EN / 中文) | V19 API | Variants | Impact | Repo | Prio | Headless |
|---|---|---|---|---|---|---|---|
| `hole_standard` | Standard holes (simple, counterbore, countersink, tapped, cosmetic thread) / 标准孔/螺纹 | `StandardHoles.Create(nomFaceToLocations, StandardHolesOptions)`<br>`StandardHoles.Modify*`<br>`StandardHoles.Find/Convert`<br>`(raw API) Hole.Create` | 14_hole_simple_001_d6_depth10<br>14_hole_cbore_001_M6<br>14_hole_csink_001_90deg<br>14_hole_tapped_001_M8_cosmetic | geometry (SAB) + document.xml tree entries (hole feature data + cylinder/cone faces) | partial | P1 | needs selection setup (face + location map) - StandardHolesOptions API to verify |

## 15_mesh_facet — NEW: Facet/mesh bodies (DesignMesh)

| id | Feature (EN / 中文) | V19 API | Variants | Impact | Repo | Prio | Headless |
|---|---|---|---|---|---|---|---|
| `mesh_facet` | Facet (mesh) bodies: convert solid->mesh, reduce, smooth, thicken, boolean / 网格体 | `FacetConvert.Create`<br>`FacetReduce/FacetSmooth/FacetRemesh/FacetMerge/FacetSubtract/FacetThicken`<br>`STLFile.Import/Insert` | 15_mesh_convert_001_block<br>15_mesh_stl_import_001<br>15_mesh_reduce_001_50pct | geometry (SAB) + document.xml tree entries (DesignMesh storage) | none | P2 | yes |

## Combination cases (`20_combo`)

| case | description | features | prio | headless |
|---|---|---|---|---|
| `20_combo_bracket_001_sketch_pull_round_hole` | L-bracket: sketch L profile, pull 30, round inner edge r5, 2 through holes r3 | sk_line, pull_extrude_face, edge_round, pull_extrude_cut | P0 | needs selection setup |
| `20_combo_flange_002_revolve_pattern_chamfer` | Pipe flange: revolve profile, circular pattern of 6 bolt holes, chamfer outer edge | pull_revolve, pull_extrude_cut, mp_pattern_circular, edge_chamfer | P0 | needs selection setup |
| `20_combo_plate_003_linear_pattern_holes_round` | Plate 100x60x5 with 3x4 hole pattern and all-edge rounds | prim_block, pull_extrude_cut, mp_pattern_linear, edge_round | P0 | needs selection setup |
| `20_combo_housing_004_block_shell_round` | Housing: block, round vertical edges r8, shell open top t2 | prim_block, edge_round, so_shell | P0 | needs selection setup |
| `20_combo_bool_005_block_cyl_sphere` | Boolean chain: block + cylinder boss merge, subtract sphere, intersect with cylinder | bool_merge, bool_subtract, bool_intersect | P0 | yes |
| `20_combo_shaft_006_revolve_chamfer_keyway` | Stepped shaft: revolve 3 diameters, chamfer ends, keyway pocket | pull_revolve, edge_chamfer, pull_extrude_cut | P0 | needs selection setup |
| `20_combo_spline_007_spline_extrude_round` | Spline cam: closed spline profile extruded 10, rounded r1 | sk_spline, pull_extrude_face, edge_round | P0 | needs selection setup |
| `20_combo_loft_008_loft_shell` | Bottle: loft rect->circle->circle, shell open top 1mm | pull_loft, so_shell | P1 | needs selection setup |
| `20_combo_sweep_009_pipe_bend` | Bent pipe: sweep circle along line-arc-line path, shell both ends | pull_sweep, so_shell | P1 | needs selection setup |
| `20_combo_mirror_010_half_model_mirror_merge` | Half model mirrored about YZ and merged | mp_mirror, bool_merge | P0 | needs selection setup |
| `20_combo_split_011_split_multi_body_names_colors` | Block split into 3 bodies by 2 planes, each renamed + colored | bool_split_body, doc_rename, doc_colors | P0 | yes |
| `20_combo_doc_012_layers_colors_named_selections` | Doc attributes: 3 bodies on 2 layers, face colors, 3 named selections (inlet/outlet/wall) | doc_layers, doc_colors, doc_named_selection, doc_rename | P0 | yes |
| `20_combo_doc_013_datums_named_selection_on_edges` | Datum plane + axis + named selection of edges on filleted block | doc_datum, edge_round, doc_named_selection | P1 | needs selection setup |
| `20_combo_asm_014_two_components` | 2-component assembly: plate + boss in separate components, renamed | asm_component, doc_rename | P0 | yes |
| `20_combo_asm_015_instances_pattern` | Assembly with 1 part definition instanced 4x (translated + rotated) | asm_component, asm_instance, mp_translate, mp_rotate | P0 | needs selection setup |
| `20_combo_asm_016_nested_3levels_colors_layers` | Nested assembly 3 levels, bodies colored + layered | asm_component, doc_layers, doc_colors | P1 | yes |
| `20_combo_asm_017_mates_align_tangent` | 2-component assembly with align + tangent conditions | asm_component, asm_conditions | P0 | needs selection setup (raw API conditions, verify) |
| `20_combo_sm_018_sheetmetal_bracket` | Sheet metal bracket: convert plate, 2 flanges, relief, unfold | sm_all | P1 | GUI-only |
| `20_combo_beam_019_frame_with_profiles` | Beam frame: rectangular frame of 4 lines + 2 diagonals, I profile + rect tube | beam_profile, beam_create, sk_datum_curve | P1 | needs selection setup |
| `20_combo_prep_020_midsurface_share_topology` | Plate assembly midsurfaced and topology shared | rp_midsurface, rp_share_topology | P1 | yes |
| `20_combo_prep_021_enclosure_named_selection` | CFD prep: body + box enclosure (cushion 20) + named selections inlet/outlet | rp_volume_extract, doc_named_selection | P1 | needs selection setup |
| `20_combo_hole_022_holes_pattern_plate` | Plate with counterbored M6 hole circular-patterned 4x | hole_standard, mp_pattern_circular | P1 | needs selection setup |
| `20_combo_helix_023_spring_ends_ground` | Spring: helix sweep of circle, ends cut flat by split planes | pull_helix, bool_split_body | P1 | needs selection setup |
| `20_combo_draft_024_molded_part` | Molded box: extrude, draft 3deg, round r2, shell t1.5 | so_draft, edge_round, so_shell | P1 | needs selection setup |
| `20_combo_surface_025_sheets_stitch_thicken` | Sheets: 2 planar + 1 cylindrical surface stitched, thickened 2mm | prim_planar_body, sc_surfaces, rp_fix, so_thicken | P2 | needs selection setup |
| `20_combo_wrap_026_cylinder_wrap_text_pull` | Cylinder with wrapped rectangle imprint pulled 1mm | sc_project_wrap, pull_face_offset | P2 | needs selection setup |
| `20_combo_units_027_inch_doc_primitives` | Inch document with block+cylinder (unit factor check) | doc_units, prim_block, prim_cylinder | P1 | unknown (units setter) |
| `20_combo_multi_028_many_bodies_8` | 8 bodies (mixed primitives) in root, each named/colored - id allocation stress | prim_block, prim_cylinder, prim_sphere, doc_rename, doc_colors | P0 | yes |
| `20_combo_multi_029_many_components_8` | 8 components each with one body (IMPROVEMENT_PRIORITIES P0-1 id collision scenario) | asm_component | P0 | yes |
| `20_combo_edit_030_pull_after_pattern` | Pattern of bosses then pull base face + round (pattern relation survives edit) | mp_pattern_linear, pull_face_offset, edge_round | P1 | needs selection setup |
| `20_combo_view_031_named_views_section` | Named views + section plane on assembly | doc_named_view, asm_component | P1 | needs GUI window? (test) |
| `20_combo_mesh_032_mesh_plus_solid` | Document with solid body + facet body converted from a copy | mesh_facet, prim_cylinder | P2 | yes |

## Not scriptable in V19 (GUI-only / needs non-scripting API)

- **Sheet metal**: no SheetMetal* class among the 171 Scripting Commands types; the raw API only exposes read-side `SheetMetalAspect/SheetMetalFeature/Bend` (no Create) -> GUI-only for generation.
- **Assembly conditions**: no Scripting command (`Constraint.*` are *sketch* constraints) BUT the raw API has `AlignCondition/TangentCondition/OrientCondition/AnchorCondition/RigidCondition/GearCondition.Create` -> feasible via raw API from the RunScript host (to verify).
- **Variable-radius round**: only ConstantRound / FullRound / Chamfer exist.
- **Material**: via raw API `DocumentMaterial.Create` + `DesignBody.Material`; **document units setter**: not found yet (UnitsHelper is read-only).
- **Named views**: ViewHelper.CreateNamedView exists but needs a window — test in GUI mode.

## Estimate

- SpaceClaim launch overhead measured in 00_smoke: ~85 s start + ~36 s exit ≈ 2 min; smoke script body 23 s (includes first-command warm-up).
- Plan: one launch per category batch (≤ ~25 cases per launch, `DocumentHelper.CreateNewDocument` + `CloseDocument` per case), assume ~10–15 s/case in-process.
- Scriptable cases: 186 single (excl. done smoke + 3 GUI-only sheet-metal) + 31 combos (excl. 1 GUI-only) ≈ 217 cases.
- Launches: ~14 (one per category 01–15, combos split in 2) → ~28 min overhead + ~217×12 s ≈ 43 min in-process → **~75 min pure run time**; budget 2–4 h wall clock including fix-up re-runs of selection-heavy categories.
