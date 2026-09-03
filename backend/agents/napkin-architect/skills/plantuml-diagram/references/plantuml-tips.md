# PlantUML 技巧

## 布局

- `left to right direction` / `top to bottom direction`
- `together { ... }` 拉近相关节点
- `hide empty description` 减少空白

## 序列图

```plantuml
@startuml
autonumber
participant A
participant B
A -> B: request
activate B
B --> A: response
deactivate B
@enduml
```

- `->` 实线，`-->` 虚线；`->>` 异步风格。
- `note right of A: 说明`

## 部署

```plantuml
@startuml
node "K8s Cluster" {
  node "Pod" as pod {
    component app
  }
}
cloud "CDN"
database "RDS"
@enduml
```

## 稳定性

- 避免未文档化的 beta 指令。
- 大型图：拆成多张或 `package`/`together` 分组。
- 颜色：`skinparam` 少而精；C4 已有主题时不要重复覆盖。
