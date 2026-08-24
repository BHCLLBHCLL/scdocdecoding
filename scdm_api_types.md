# SpaceClaim 2019 R3 API surface (reverse-engineered via .NET reflection)

Source: `C:\Program Files\ANSYS Inc\v195\scdm\SpaceClaim.Api.V19\SpaceClaim.Api.V19.dll` (v19.1.17034.0).
Used as behavioral spec for the scdm OCCT-based kernel. No SpaceClaim code is shipped.

## SpaceClaim.Api.V19.SelectionFilterType


## SpaceClaim.Api.V19.InteractionMode


## SpaceClaim.Api.V19.DesignBody

- Method SpaceClaim.Api.V19.Moniker`1[SpaceClaim.Api.V19.DesignBody] get_Moniker()
- Method SpaceClaim.Api.V19.IDesignBody GetOccurrence(System.Collections.Generic.IList`1[SpaceClaim.Api.V19.Instance])
- Method SpaceClaim.Api.V19.IDesignBody GetOccurrence(SpaceClaim.Api.V19.Instance)
- Method SpaceClaim.Api.V19.IDesignBody GetOccurrence(SpaceClaim.Api.V19.IDocObject)
- Method SpaceClaim.Api.V19.DesignBody Create(SpaceClaim.Api.V19.Part, string, SpaceClaim.Api.V19.Modeler.Body)
- Method System.Collections.Generic.IDictionary`2[SpaceClaim.Api.V19.Modeler.Face,SpaceClaim.Api.V19.Modeler.FaceTessellation] GetTessellation(System.Collections.Generic.ICollection`1[SpaceClaim.Api.V19.Modeler.Face])
- Method SpaceClaim.Api.V19.Geometry.Box GetTessellationBoundingBox(SpaceClaim.Api.V19.Geometry.Matrix, Boolean)
- Method System.Collections.Generic.IDictionary`2[SpaceClaim.Api.V19.Modeler.Edge.ICollection`1[SpaceClaim.Api.V19.Geometry.Point]] GetEdgeTessellation(System.Collections.Generic.ICollection`1[SpaceClaim.Api.V19.Modeler.Edge])
- Method Boolean get_IsLocked()
- Method Void set_IsLocked(Boolean)
- Method Void Save(SpaceClaim.Api.V19.Modeler.BodySaveFormat, string)
- Method SpaceClaim.Api.V19.MidSurfaceAspect get_MidSurface()
- Method SpaceClaim.Api.V19.VolumeExtractionAspect get_VolumeExtraction()
- Method SpaceClaim.Api.V19.EnclosureAspect get_Enclosure()
- Method System.Collections.Generic.ICollection`1[SpaceClaim.Api.V19.Hole] IdentifyHoles(SpaceClaim.Api.V19.IdentifyHoleOptions)
- Method SpaceClaim.Api.V19.Part get_Parent()
- Method System.Collections.Generic.ICollection`1[SpaceClaim.Api.V19.DesignFace] get_Faces()
- Method System.Collections.Generic.ICollection`1[SpaceClaim.Api.V19.DesignEdge] get_Edges()
- Method SpaceClaim.Api.V19.DesignFace GetDesignFace(SpaceClaim.Api.V19.Modeler.Face)
- Method SpaceClaim.Api.V19.DesignEdge GetDesignEdge(SpaceClaim.Api.V19.Modeler.Edge)
- Method SpaceClaim.Api.V19.DesignBody GetDesignBody(SpaceClaim.Api.V19.Modeler.Body)
- Method SpaceClaim.Api.V19.BodyStyle get_Style()
- Method Void set_Style(SpaceClaim.Api.V19.BodyStyle)
- Method SpaceClaim.Api.V19.DocumentMaterial get_Material()
- Method Void set_Material(SpaceClaim.Api.V19.DocumentMaterial)
- Method Void Transform(SpaceClaim.Api.V19.Geometry.Matrix)
- Method Void Scale(SpaceClaim.Api.V19.Geometry.Frame, Double, Double, Double)
- Method string get_Name()
- Method Void set_Name(string)
- Method SpaceClaim.Api.V19.Modeler.Body get_Shape()
- Method SpaceClaim.Api.V19.Layer get_Layer()
- Method Void set_Layer(SpaceClaim.Api.V19.Layer)
- Method System.Nullable`1[bool] get_DefaultVisibility()
- Method System.Nullable`1[System.Drawing.Color] GetColor(SpaceClaim.Api.V19.IAppearanceContext)
- Method Void SetColor(SpaceClaim.Api.V19.IAppearanceContext, System.Nullable`1[System.Drawing.Color])
- Method SpaceClaim.Api.V19.SurfaceMaterial get_SurfaceMaterial()
- Method System.Nullable`1[bool] GetVisibility(SpaceClaim.Api.V19.IAppearanceContext)
- Method Void SetVisibility(SpaceClaim.Api.V19.IAppearanceContext, System.Nullable`1[bool])
- Method Boolean IsVisible(SpaceClaim.Api.V19.IAppearanceContext)
- Method SpaceClaim.Api.V19.MassProperties get_MassProperties()
- Method Boolean get_CanSuppress()
- Method Boolean get_IsSuppressed()
- Method Void set_IsSuppressed(Boolean)
- Property SpaceClaim.Api.V19.Moniker`1[SpaceClaim.Api.V19.DesignBody] Moniker
- Property Boolean IsLocked
- Property SpaceClaim.Api.V19.MidSurfaceAspect MidSurface
- Property SpaceClaim.Api.V19.VolumeExtractionAspect VolumeExtraction
- Property SpaceClaim.Api.V19.EnclosureAspect Enclosure
- Property SpaceClaim.Api.V19.Part Parent
- Property System.Collections.Generic.ICollection`1[SpaceClaim.Api.V19.DesignFace] Faces
- Property System.Collections.Generic.ICollection`1[SpaceClaim.Api.V19.DesignEdge] Edges
- Property SpaceClaim.Api.V19.BodyStyle Style
- Property SpaceClaim.Api.V19.DocumentMaterial Material
- Property string Name
- Property SpaceClaim.Api.V19.Modeler.Body Shape
- Property SpaceClaim.Api.V19.Layer Layer
- Property System.Nullable`1[bool] DefaultVisibility
- Property SpaceClaim.Api.V19.SurfaceMaterial SurfaceMaterial
- Property SpaceClaim.Api.V19.MassProperties MassProperties
- Property Boolean CanSuppress
- Property Boolean IsSuppressed

## SpaceClaim.Api.V19.DesignEdge

- Method SpaceClaim.Api.V19.Moniker`1[SpaceClaim.Api.V19.DesignEdge] get_Moniker()
- Method SpaceClaim.Api.V19.IDesignEdge GetOccurrence(System.Collections.Generic.IList`1[SpaceClaim.Api.V19.Instance])
- Method SpaceClaim.Api.V19.IDesignEdge GetOccurrence(SpaceClaim.Api.V19.Instance)
- Method SpaceClaim.Api.V19.IDesignEdge GetOccurrence(SpaceClaim.Api.V19.IDocObject)
- Method SpaceClaim.Api.V19.DesignBody get_Parent()
- Method System.Collections.Generic.ICollection`1[SpaceClaim.Api.V19.DesignFace] get_Faces()
- Method SpaceClaim.Api.V19.Modeler.Edge get_Shape()
- Method string get_ExportIdentifier()
- Property SpaceClaim.Api.V19.Moniker`1[SpaceClaim.Api.V19.DesignEdge] Moniker
- Property SpaceClaim.Api.V19.DesignBody Parent
- Property System.Collections.Generic.ICollection`1[SpaceClaim.Api.V19.DesignFace] Faces
- Property SpaceClaim.Api.V19.Modeler.Edge Shape
- Property string ExportIdentifier

## SpaceClaim.Api.V19.DesignFace

- Method SpaceClaim.Api.V19.Moniker`1[SpaceClaim.Api.V19.DesignFace] get_Moniker()
- Method SpaceClaim.Api.V19.IDesignFace GetOccurrence(System.Collections.Generic.IList`1[SpaceClaim.Api.V19.Instance])
- Method SpaceClaim.Api.V19.IDesignFace GetOccurrence(SpaceClaim.Api.V19.Instance)
- Method SpaceClaim.Api.V19.IDesignFace GetOccurrence(SpaceClaim.Api.V19.IDocObject)
- Method SpaceClaim.Api.V19.DesignBody get_Parent()
- Method System.Collections.Generic.ICollection`1[SpaceClaim.Api.V19.DesignEdge] get_Edges()
- Method System.Collections.Generic.ICollection`1[SpaceClaim.Api.V19.DesignFace] get_AdjacentFaces()
- Method System.Nullable`1[System.Drawing.Color] GetColor(SpaceClaim.Api.V19.IAppearanceContext)
- Method Void SetColor(SpaceClaim.Api.V19.IAppearanceContext, System.Nullable`1[System.Drawing.Color])
- Method SpaceClaim.Api.V19.Modeler.Face get_Shape()
- Method string get_ExportIdentifier()
- Method Double get_Area()
- Method Double get_Perimeter()
- Method SpaceClaim.Api.V19.SurfaceMaterial get_SurfaceMaterial()
- Property SpaceClaim.Api.V19.Moniker`1[SpaceClaim.Api.V19.DesignFace] Moniker
- Property SpaceClaim.Api.V19.DesignBody Parent
- Property System.Collections.Generic.ICollection`1[SpaceClaim.Api.V19.DesignEdge] Edges
- Property System.Collections.Generic.ICollection`1[SpaceClaim.Api.V19.DesignFace] AdjacentFaces
- Property SpaceClaim.Api.V19.Modeler.Face Shape
- Property string ExportIdentifier
- Property Double Area
- Property Double Perimeter
- Property SpaceClaim.Api.V19.SurfaceMaterial SurfaceMaterial

## SpaceClaim.Api.V19.Modeler.Shell

- Method System.Collections.Generic.ICollection`1[SpaceClaim.Api.V19.Modeler.Face] get_Faces()
- Method System.Collections.Generic.ICollection`1[SpaceClaim.Api.V19.Modeler.Edge] get_Edges()
- Method System.Collections.Generic.ICollection`1[SpaceClaim.Api.V19.Modeler.Vertex] get_Vertices()
- Method SpaceClaim.Api.V19.Modeler.ShellType get_Type()
- Property System.Collections.Generic.ICollection`1[SpaceClaim.Api.V19.Modeler.Face] Faces
- Property System.Collections.Generic.ICollection`1[SpaceClaim.Api.V19.Modeler.Edge] Edges
- Property System.Collections.Generic.ICollection`1[SpaceClaim.Api.V19.Modeler.Vertex] Vertices
- Property SpaceClaim.Api.V19.Modeler.ShellType Type

## SpaceClaim.Api.V19.Modeler.ShellType


## SpaceClaim.Api.V19.Geometry.Helix


## SpaceClaim.Api.V19.Geometry.Transformations


## SpaceClaim.Api.V19.Geometry.Box

- Method Boolean op_Equality(SpaceClaim.Api.V19.Geometry.Box, SpaceClaim.Api.V19.Geometry.Box)
- Method Boolean op_Inequality(SpaceClaim.Api.V19.Geometry.Box, SpaceClaim.Api.V19.Geometry.Box)
- Method Boolean Equals(SpaceClaim.Api.V19.Geometry.Box)
- Method Boolean Equals(System.Object)
- Method Int32 GetHashCode()
- Method SpaceClaim.Api.V19.Geometry.Box Create(SpaceClaim.Api.V19.Geometry.Point)
- Method SpaceClaim.Api.V19.Geometry.Box Create(SpaceClaim.Api.V19.Geometry.Point[])
- Method SpaceClaim.Api.V19.Geometry.Box Create(System.Collections.Generic.ICollection`1[SpaceClaim.Api.V19.Geometry.Point])
- Method Boolean get_IsEmpty()
- Method SpaceClaim.Api.V19.Geometry.Point get_Center()
- Method SpaceClaim.Api.V19.Geometry.Vector get_Size()
- Method SpaceClaim.Api.V19.Geometry.Point get_MinCorner()
- Method SpaceClaim.Api.V19.Geometry.Point get_MaxCorner()
- Method System.Collections.Generic.ICollection`1[SpaceClaim.Api.V19.Geometry.Point] get_Corners()
- Method Boolean ContainsPoint(SpaceClaim.Api.V19.Geometry.Point)
- Method Boolean IntersectsPlane(SpaceClaim.Api.V19.Geometry.Plane)
- Method SpaceClaim.Api.V19.Geometry.Box Inflate(Double)
- Method SpaceClaim.Api.V19.Geometry.Box op_BitwiseOr(SpaceClaim.Api.V19.Geometry.Box, SpaceClaim.Api.V19.Geometry.Box)
- Method SpaceClaim.Api.V19.Geometry.Box op_BitwiseAnd(SpaceClaim.Api.V19.Geometry.Box, SpaceClaim.Api.V19.Geometry.Box)
- Property Boolean IsEmpty
- Property SpaceClaim.Api.V19.Geometry.Point Center
- Property SpaceClaim.Api.V19.Geometry.Vector Size
- Property SpaceClaim.Api.V19.Geometry.Point MinCorner
- Property SpaceClaim.Api.V19.Geometry.Point MaxCorner
- Property System.Collections.Generic.ICollection`1[SpaceClaim.Api.V19.Geometry.Point] Corners

## SpaceClaim.Api.V19.Geometry.Cone

- Method SpaceClaim.Api.V19.Geometry.Cone op_Multiply(SpaceClaim.Api.V19.Geometry.Matrix, SpaceClaim.Api.V19.Geometry.Cone)
- Method SpaceClaim.Api.V19.Geometry.Cone CreateTransformedCopy(SpaceClaim.Api.V19.Geometry.Matrix)
- Method SpaceClaim.Api.V19.Geometry.Cone Create(SpaceClaim.Api.V19.Geometry.Frame, Double, Double)
- Method Double get_Radius()
- Method Double get_HalfAngle()
- Method Double GetLength(SpaceClaim.Api.V19.Geometry.PointUV, SpaceClaim.Api.V19.Geometry.PointUV)
- Method Boolean TryOffsetParam(SpaceClaim.Api.V19.Geometry.PointUV, SpaceClaim.Api.V19.Geometry.DirectionUV, Double, SpaceClaim.Api.V19.Geometry.PointUV ByRef)
- Method SpaceClaim.Api.V19.Geometry.Frame get_Frame()
- Method SpaceClaim.Api.V19.Geometry.Line get_Axis()
- Property Double Radius
- Property Double HalfAngle
- Property SpaceClaim.Api.V19.Geometry.Frame Frame
- Property SpaceClaim.Api.V19.Geometry.Line Axis

## SpaceClaim.Api.V19.Geometry.Cylinder

- Method SpaceClaim.Api.V19.Geometry.Cylinder op_Multiply(SpaceClaim.Api.V19.Geometry.Matrix, SpaceClaim.Api.V19.Geometry.Cylinder)
- Method SpaceClaim.Api.V19.Geometry.Cylinder CreateTransformedCopy(SpaceClaim.Api.V19.Geometry.Matrix)
- Method SpaceClaim.Api.V19.Geometry.Cylinder Create(SpaceClaim.Api.V19.Geometry.Frame, Double)
- Method Double get_Radius()
- Method Double GetLength(SpaceClaim.Api.V19.Geometry.PointUV, SpaceClaim.Api.V19.Geometry.PointUV)
- Method Boolean TryOffsetParam(SpaceClaim.Api.V19.Geometry.PointUV, SpaceClaim.Api.V19.Geometry.DirectionUV, Double, SpaceClaim.Api.V19.Geometry.PointUV ByRef)
- Method SpaceClaim.Api.V19.Geometry.Frame get_Frame()
- Method SpaceClaim.Api.V19.Geometry.Line get_Axis()
- Property Double Radius
- Property SpaceClaim.Api.V19.Geometry.Frame Frame
- Property SpaceClaim.Api.V19.Geometry.Line Axis

## SpaceClaim.Api.V19.Geometry.Direction

- Method Boolean op_Equality(SpaceClaim.Api.V19.Geometry.Direction, SpaceClaim.Api.V19.Geometry.Direction)
- Method Boolean op_Inequality(SpaceClaim.Api.V19.Geometry.Direction, SpaceClaim.Api.V19.Geometry.Direction)
- Method Boolean Equals(SpaceClaim.Api.V19.Geometry.Direction)
- Method Boolean Equals(System.Object)
- Method Int32 GetHashCode()
- Method SpaceClaim.Api.V19.Geometry.Direction Create(Double, Double, Double)
- Method Double get_X()
- Method Double get_Y()
- Method Double get_Z()
- Method Double get_Item(Int32)
- Method Boolean get_IsZero()
- Method SpaceClaim.Api.V19.Geometry.Vector get_UnitVector()
- Method SpaceClaim.Api.V19.Geometry.Direction get_ArbitraryPerpendicular()
- Method SpaceClaim.Api.V19.Geometry.Direction op_UnaryPlus(SpaceClaim.Api.V19.Geometry.Direction)
- Method SpaceClaim.Api.V19.Geometry.Direction op_UnaryNegation(SpaceClaim.Api.V19.Geometry.Direction)
- Method SpaceClaim.Api.V19.Geometry.Vector op_Multiply(SpaceClaim.Api.V19.Geometry.Direction, Double)
- Method SpaceClaim.Api.V19.Geometry.Vector op_Multiply(Double, SpaceClaim.Api.V19.Geometry.Direction)
- Method SpaceClaim.Api.V19.Geometry.Vector op_Division(SpaceClaim.Api.V19.Geometry.Direction, Double)
- Method Boolean IsParallel(SpaceClaim.Api.V19.Geometry.Direction)
- Method Boolean IsPerpendicular(SpaceClaim.Api.V19.Geometry.Direction)
- Method string ToString()
- Method SpaceClaim.Api.V19.Geometry.Direction Cross(SpaceClaim.Api.V19.Geometry.Direction, SpaceClaim.Api.V19.Geometry.Direction)
- Property Double X
- Property Double Y
- Property Double Z
- Property Double Item [Int32]
- Property Boolean IsZero
- Property SpaceClaim.Api.V19.Geometry.Vector UnitVector
- Property SpaceClaim.Api.V19.Geometry.Direction ArbitraryPerpendicular

## SpaceClaim.Api.V19.Geometry.Frame

- Method Boolean op_Equality(SpaceClaim.Api.V19.Geometry.Frame, SpaceClaim.Api.V19.Geometry.Frame)
- Method Boolean op_Inequality(SpaceClaim.Api.V19.Geometry.Frame, SpaceClaim.Api.V19.Geometry.Frame)
- Method Boolean Equals(SpaceClaim.Api.V19.Geometry.Frame)
- Method Boolean Equals(System.Object)
- Method Int32 GetHashCode()
- Method SpaceClaim.Api.V19.Geometry.Frame Create(SpaceClaim.Api.V19.Geometry.Point, SpaceClaim.Api.V19.Geometry.Direction, SpaceClaim.Api.V19.Geometry.Direction)
- Method SpaceClaim.Api.V19.Geometry.Frame Create(SpaceClaim.Api.V19.Geometry.Point, SpaceClaim.Api.V19.Geometry.Direction)
- Method SpaceClaim.Api.V19.Geometry.Point get_Origin()
- Method SpaceClaim.Api.V19.Geometry.Direction get_DirX()
- Method SpaceClaim.Api.V19.Geometry.Direction get_DirY()
- Method SpaceClaim.Api.V19.Geometry.Direction get_DirZ()
- Method SpaceClaim.Api.V19.Geometry.Line get_AxisX()
- Method SpaceClaim.Api.V19.Geometry.Line get_AxisY()
- Method SpaceClaim.Api.V19.Geometry.Line get_AxisZ()
- Property SpaceClaim.Api.V19.Geometry.Point Origin
- Property SpaceClaim.Api.V19.Geometry.Direction DirX
- Property SpaceClaim.Api.V19.Geometry.Direction DirY
- Property SpaceClaim.Api.V19.Geometry.Direction DirZ
- Property SpaceClaim.Api.V19.Geometry.Line AxisX
- Property SpaceClaim.Api.V19.Geometry.Line AxisY
- Property SpaceClaim.Api.V19.Geometry.Line AxisZ

## SpaceClaim.Api.V19.Geometry.Plane

- Method SpaceClaim.Api.V19.Geometry.Plane get_PlaneXY()
- Method SpaceClaim.Api.V19.Geometry.Plane get_PlaneYZ()
- Method SpaceClaim.Api.V19.Geometry.Plane get_PlaneZX()
- Method SpaceClaim.Api.V19.Geometry.Plane op_Multiply(SpaceClaim.Api.V19.Geometry.Matrix, SpaceClaim.Api.V19.Geometry.Plane)
- Method SpaceClaim.Api.V19.Geometry.Plane CreateTransformedCopy(SpaceClaim.Api.V19.Geometry.Matrix)
- Method SpaceClaim.Api.V19.Geometry.Plane Create(SpaceClaim.Api.V19.Geometry.Frame)
- Method Double GetLength(SpaceClaim.Api.V19.Geometry.PointUV, SpaceClaim.Api.V19.Geometry.PointUV)
- Method Boolean TryOffsetParam(SpaceClaim.Api.V19.Geometry.PointUV, SpaceClaim.Api.V19.Geometry.DirectionUV, Double, SpaceClaim.Api.V19.Geometry.PointUV ByRef)
- Method System.Collections.Generic.ICollection`1[SpaceClaim.Api.V19.Geometry.IntPoint`2[SpaceClaim.Api.V19.Geometry.SurfaceEvaluation,SpaceClaim.Api.V19.Geometry.CurveEvaluation]] IntersectCurve(SpaceClaim.Api.V19.Geometry.Curve)
- Method Boolean TryIntersectLine(SpaceClaim.Api.V19.Geometry.Line, SpaceClaim.Api.V19.Geometry.Point ByRef)
- Method SpaceClaim.Api.V19.Geometry.Frame get_Frame()
- Property SpaceClaim.Api.V19.Geometry.Plane PlaneXY
- Property SpaceClaim.Api.V19.Geometry.Plane PlaneYZ
- Property SpaceClaim.Api.V19.Geometry.Plane PlaneZX
- Property SpaceClaim.Api.V19.Geometry.Frame Frame

## SpaceClaim.Api.V19.Geometry.Sphere

- Method SpaceClaim.Api.V19.Geometry.Sphere op_Multiply(SpaceClaim.Api.V19.Geometry.Matrix, SpaceClaim.Api.V19.Geometry.Sphere)
- Method SpaceClaim.Api.V19.Geometry.Sphere CreateTransformedCopy(SpaceClaim.Api.V19.Geometry.Matrix)
- Method SpaceClaim.Api.V19.Geometry.Sphere Create(SpaceClaim.Api.V19.Geometry.Frame, Double)
- Method Double get_Radius()
- Method Double GetLength(SpaceClaim.Api.V19.Geometry.PointUV, SpaceClaim.Api.V19.Geometry.PointUV)
- Method Boolean TryOffsetParam(SpaceClaim.Api.V19.Geometry.PointUV, SpaceClaim.Api.V19.Geometry.DirectionUV, Double, SpaceClaim.Api.V19.Geometry.PointUV ByRef)
- Method SpaceClaim.Api.V19.Geometry.Frame get_Frame()
- Property Double Radius
- Property SpaceClaim.Api.V19.Geometry.Frame Frame

## SpaceClaim.Api.V19.Geometry.Torus

- Method SpaceClaim.Api.V19.Geometry.Torus op_Multiply(SpaceClaim.Api.V19.Geometry.Matrix, SpaceClaim.Api.V19.Geometry.Torus)
- Method SpaceClaim.Api.V19.Geometry.Torus CreateTransformedCopy(SpaceClaim.Api.V19.Geometry.Matrix)
- Method SpaceClaim.Api.V19.Geometry.Torus Create(SpaceClaim.Api.V19.Geometry.Frame, Double, Double)
- Method Double get_MajorRadius()
- Method Double get_MinorRadius()
- Method SpaceClaim.Api.V19.Geometry.Circle get_Circle()
- Method Double GetLength(SpaceClaim.Api.V19.Geometry.PointUV, SpaceClaim.Api.V19.Geometry.PointUV)
- Method Boolean TryOffsetParam(SpaceClaim.Api.V19.Geometry.PointUV, SpaceClaim.Api.V19.Geometry.DirectionUV, Double, SpaceClaim.Api.V19.Geometry.PointUV ByRef)
- Method SpaceClaim.Api.V19.Geometry.Frame get_Frame()
- Method SpaceClaim.Api.V19.Geometry.Plane get_Plane()
- Method SpaceClaim.Api.V19.Geometry.Line get_Axis()
- Property Double MajorRadius
- Property Double MinorRadius
- Property SpaceClaim.Api.V19.Geometry.Circle Circle
- Property SpaceClaim.Api.V19.Geometry.Frame Frame
- Property SpaceClaim.Api.V19.Geometry.Plane Plane
- Property SpaceClaim.Api.V19.Geometry.Line Axis

## SpaceClaim.Api.V19.Geometry.Vector

- Method Boolean op_Equality(SpaceClaim.Api.V19.Geometry.Vector, SpaceClaim.Api.V19.Geometry.Vector)
- Method Boolean op_Inequality(SpaceClaim.Api.V19.Geometry.Vector, SpaceClaim.Api.V19.Geometry.Vector)
- Method Boolean Equals(SpaceClaim.Api.V19.Geometry.Vector)
- Method Boolean Equals(System.Object)
- Method Int32 GetHashCode()
- Method SpaceClaim.Api.V19.Geometry.Vector Create(Double, Double, Double)
- Method Double get_X()
- Method Double get_Y()
- Method Double get_Z()
- Method Double get_Item(Int32)
- Method SpaceClaim.Api.V19.Geometry.Direction get_Direction()
- Method Double get_Magnitude()
- Method SpaceClaim.Api.V19.Geometry.Vector Project(SpaceClaim.Api.V19.Geometry.Direction)
- Method SpaceClaim.Api.V19.Geometry.Vector op_UnaryPlus(SpaceClaim.Api.V19.Geometry.Vector)
- Method SpaceClaim.Api.V19.Geometry.Vector op_UnaryNegation(SpaceClaim.Api.V19.Geometry.Vector)
- Method SpaceClaim.Api.V19.Geometry.Vector op_Addition(SpaceClaim.Api.V19.Geometry.Vector, SpaceClaim.Api.V19.Geometry.Vector)
- Method SpaceClaim.Api.V19.Geometry.Vector op_Subtraction(SpaceClaim.Api.V19.Geometry.Vector, SpaceClaim.Api.V19.Geometry.Vector)
- Method SpaceClaim.Api.V19.Geometry.Vector op_Multiply(SpaceClaim.Api.V19.Geometry.Vector, Double)
- Method SpaceClaim.Api.V19.Geometry.Vector op_Multiply(Double, SpaceClaim.Api.V19.Geometry.Vector)
- Method SpaceClaim.Api.V19.Geometry.Vector op_Division(SpaceClaim.Api.V19.Geometry.Vector, Double)
- Method Double Dot(SpaceClaim.Api.V19.Geometry.Vector, SpaceClaim.Api.V19.Geometry.Vector)
- Method SpaceClaim.Api.V19.Geometry.Vector Cross(SpaceClaim.Api.V19.Geometry.Vector, SpaceClaim.Api.V19.Geometry.Vector)
- Method string ToString()
- Property Double X
- Property Double Y
- Property Double Z
- Property Double Item [Int32]
- Property SpaceClaim.Api.V19.Geometry.Direction Direction
- Property Double Magnitude

## SpaceClaim.Api.V19.Geometry.Matrix

- Method Boolean op_Equality(SpaceClaim.Api.V19.Geometry.Matrix, SpaceClaim.Api.V19.Geometry.Matrix)
- Method Boolean op_Inequality(SpaceClaim.Api.V19.Geometry.Matrix, SpaceClaim.Api.V19.Geometry.Matrix)
- Method Boolean Equals(SpaceClaim.Api.V19.Geometry.Matrix)
- Method Boolean Equals(System.Object)
- Method Int32 GetHashCode()
- Method SpaceClaim.Api.V19.Geometry.Matrix CreateTranslation(SpaceClaim.Api.V19.Geometry.Vector)
- Method SpaceClaim.Api.V19.Geometry.Matrix CreateScale(Double, SpaceClaim.Api.V19.Geometry.Point)
- Method SpaceClaim.Api.V19.Geometry.Matrix CreateScale(Double)
- Method SpaceClaim.Api.V19.Geometry.Matrix CreateRotation(SpaceClaim.Api.V19.Geometry.Line, Double)
- Method SpaceClaim.Api.V19.Geometry.Matrix CreateMapping(SpaceClaim.Api.V19.Geometry.Frame)
- Method Boolean get_IsIdentity()
- Method Boolean get_HasTranslation()
- Method Boolean get_HasScale()
- Method Boolean get_HasRotation()
- Method SpaceClaim.Api.V19.Geometry.Vector get_Translation()
- Method Double get_Scale()
- Method SpaceClaim.Api.V19.Geometry.Matrix get_Rotation()
- Method Boolean get_IsMirror()
- Method Void Decompose(SpaceClaim.Api.V19.Geometry.Vector ByRef, Double ByRef, SpaceClaim.Api.V19.Geometry.Matrix ByRef)
- Method Void Decompose(Double ByRef, SpaceClaim.Api.V19.Geometry.Vector ByRef, SpaceClaim.Api.V19.Geometry.Matrix ByRef)
- Method Void Decompose(SpaceClaim.Api.V19.Geometry.Matrix ByRef, SpaceClaim.Api.V19.Geometry.Vector ByRef, Double ByRef)
- Method Void Decompose(Double ByRef, SpaceClaim.Api.V19.Geometry.Matrix ByRef, SpaceClaim.Api.V19.Geometry.Vector ByRef)
- Method Void Decompose(SpaceClaim.Api.V19.Geometry.Vector ByRef, SpaceClaim.Api.V19.Geometry.Matrix ByRef, Double ByRef)
- Method Void Decompose(SpaceClaim.Api.V19.Geometry.Matrix ByRef, Double ByRef, SpaceClaim.Api.V19.Geometry.Vector ByRef)
- Method Double get_Item(Int32, Int32)
- Method SpaceClaim.Api.V19.Geometry.Matrix get_Inverse()
- Method Boolean TryGetRotation(SpaceClaim.Api.V19.Geometry.Line ByRef, Double ByRef)
- Method SpaceClaim.Api.V19.Geometry.Matrix op_Multiply(SpaceClaim.Api.V19.Geometry.Matrix, SpaceClaim.Api.V19.Geometry.Matrix)
- Method SpaceClaim.Api.V19.Geometry.Frame op_Multiply(SpaceClaim.Api.V19.Geometry.Matrix, SpaceClaim.Api.V19.Geometry.Frame)
- Method SpaceClaim.Api.V19.Geometry.Box op_Multiply(SpaceClaim.Api.V19.Geometry.Matrix, SpaceClaim.Api.V19.Geometry.Box)
- Method SpaceClaim.Api.V19.Geometry.Point op_Multiply(SpaceClaim.Api.V19.Geometry.Matrix, SpaceClaim.Api.V19.Geometry.Point)
- Method SpaceClaim.Api.V19.Geometry.Vector op_Multiply(SpaceClaim.Api.V19.Geometry.Matrix, SpaceClaim.Api.V19.Geometry.Vector)
- Method SpaceClaim.Api.V19.Geometry.Direction op_Multiply(SpaceClaim.Api.V19.Geometry.Matrix, SpaceClaim.Api.V19.Geometry.Direction)
- Method Double op_Multiply(SpaceClaim.Api.V19.Geometry.Matrix, Double)
- Property Boolean IsIdentity
- Property Boolean HasTranslation
- Property Boolean HasScale
- Property Boolean HasRotation
- Property SpaceClaim.Api.V19.Geometry.Vector Translation
- Property Double Scale
- Property SpaceClaim.Api.V19.Geometry.Matrix Rotation
- Property Boolean IsMirror
- Property Double Item [Int32, Int32]
- Property SpaceClaim.Api.V19.Geometry.Matrix Inverse

## SpaceClaim.Api.V19.Geometry.Point

- Method Boolean op_Equality(SpaceClaim.Api.V19.Geometry.Point, SpaceClaim.Api.V19.Geometry.Point)
- Method Boolean op_Inequality(SpaceClaim.Api.V19.Geometry.Point, SpaceClaim.Api.V19.Geometry.Point)
- Method Boolean Equals(SpaceClaim.Api.V19.Geometry.Point)
- Method Boolean Equals(System.Object)
- Method Int32 GetHashCode()
- Method SpaceClaim.Api.V19.Geometry.Point Create(Double, Double, Double)
- Method Double get_X()
- Method Double get_Y()
- Method Double get_Z()
- Method Double get_Item(Int32)
- Method SpaceClaim.Api.V19.Geometry.Vector get_Vector()
- Method SpaceClaim.Api.V19.Geometry.Vector op_Subtraction(SpaceClaim.Api.V19.Geometry.Point, SpaceClaim.Api.V19.Geometry.Point)
- Method SpaceClaim.Api.V19.Geometry.Point op_Addition(SpaceClaim.Api.V19.Geometry.Point, SpaceClaim.Api.V19.Geometry.Vector)
- Method SpaceClaim.Api.V19.Geometry.Point op_Subtraction(SpaceClaim.Api.V19.Geometry.Point, SpaceClaim.Api.V19.Geometry.Vector)
- Method SpaceClaim.Api.V19.Geometry.Point op_Multiply(SpaceClaim.Api.V19.Geometry.Point, Double)
- Method SpaceClaim.Api.V19.Geometry.Point op_Multiply(Double, SpaceClaim.Api.V19.Geometry.Point)
- Method string ToString()
- Property Double X
- Property Double Y
- Property Double Z
- Property Double Item [Int32]
- Property SpaceClaim.Api.V19.Geometry.Vector Vector

