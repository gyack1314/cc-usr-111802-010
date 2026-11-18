# 援助地区数据约定

observation、reference、rule 三种记录分别表示观测、参照和区域规则。metric、region、unit 共同表示现有单期可比口径，来源版次与取得时间独立保留。

## 水车分配扩展

allocation 模块在既有来源存储上读取以下记录，合成分配方案：

- observation（metric 为 `tws_deficit_ratio`）：payload 含 region、unit（ratio）、value（0–1 的陆地储水低于常年比例）、baseline（start_year/end_year）与 coverage。baseline 或 coverage 缺失视为基准不明。
- population：region、unit（人）、value。
- alternative_supply：region、unit（m3/day）、value；同一地区可有多条，合计为可用替代供水；补交水源证据以新记录进入，按取得时间生效。
- fleet：trucks、capacity_per_truck（m3/day）。
- parameter：per_capita_need（L/人/天）。

可比性规则：基线年份与覆盖范围一致的地区才相互可比，名次只在同组内有效；基准无法对齐或基准不明时，方案说明比较限制，不给合并名次。分配按各区自身口径的净需求（人口×人均需求×异常比例−替代供水）比例配置整数水车，单车超出需求的部分不重复计入。

批准的方案按指纹存入 plans 表（save_plan/get_plan），方案内保留各来源 sha256 与参数，原先批准方案的依据可查；按原 known_at 复算得到同一指纹。
