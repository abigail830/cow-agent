# C4-PlantUML 速查

## 常用宏（stdlib `!include <C4/...>`）

| 文件 | 用途 |
|------|------|
| `C4_Context.puml` | 系统上下文 |
| `C4_Container.puml` | 容器图（含 Context 元素） |
| `C4_Component.puml` | 组件图 |
| `C4_Dynamic.puml` | 动态/交互 |
| `C4_Deployment.puml` | 部署 |

## 元素

```plantuml
Person(id, "名称", "可选描述")
Person_Ext(id, "外部用户")
System(id, "系统")
System_Ext(id, "外部系统")
System_Boundary(id, "边界名") { ... }
Container(id, "名称", "技术", "描述")
ContainerDb(id, "名称", "技术", "描述")
Component(id, "名称", "技术", "描述")
```

## 关系

```plantuml
Rel(from, to, "标签", "技术/协议")
Rel_U / Rel_D / Rel_L / Rel_R  ' 方向变体
BiRel(a, b, "双向")
```

## 注意

- `from`/`to` 必须是已定义 ID。
- Boundary 内元素在外部 Rel 时用边界内 ID。
- 描述参数可选；过长描述换 `\n` 分行。
