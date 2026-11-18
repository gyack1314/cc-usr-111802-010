# 援助地区指标分析

项目保存援助地区的来源版次，按资料取得时间比较单期指标并给出区域规则判断。evidence 保存来源，metrics 计算同口径偏离，context 解释当前区域规则，report 保存报告。现有实现尚不处理跨期与跨空间的综合分析。样本是合成数据。

allocation 模块在此之上提供应急水车分配：把可比的储水异常（按基线年份与覆盖范围分组，无法对齐时说明比较限制而不给合并名次）、人口暴露、可用替代供水与水车容量合成分配方案；补交水源证据后复算会说明援助量与未满足需求的变化，已批准方案按指纹留存、依据可查。

Python 3.11 以上，在项目根目录执行：

    python -m unittest discover -s tests -v
    python -m compileall -q climate_analysis tests
    python -m climate_analysis.cli inspect data/example.json
    python -m climate_analysis.cli allocate data/allocation_example.json

Dockerfile 可在 Linux 容器运行：docker build -t climate-analysis-010 .；docker run --rm climate-analysis-010。
