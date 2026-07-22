# Tune Betaflight PID from Blackbox Logs

**从 Betaflight 黑盒日志到可审计 CLI 的 Codex Skill**

[![GitHub stars](https://img.shields.io/github/stars/pokrc/tune-betaflight-pid?style=social)](https://github.com/pokrc/tune-betaflight-pid/stargazers)
[![License](https://img.shields.io/badge/license-PolyForm%20Noncommercial-orange)](LICENSE.md)
[![Betaflight](https://img.shields.io/badge/Betaflight-4.4%2F4.5-blue)](https://betaflight.com/)

把 `.bbl` 飞行数据交给 Codex，得到一份有证据、有安全门槛、可复查的 Betaflight 调参候选 CLI。它面向真实飞行中的共振、飞行声响、电机发热、D-term 噪声、RPM 滤波验证和前后日志对比。

> **定位：辅助决策，不是“一键万能预设”。** 输出必须结合机架、桨叶、电机、固件、飞行环境和电机温度进行短距离验证。

## 为什么值得使用

- **从数据出发**：读取黑盒日志中的固件、飞行窗口、频谱、陀螺仪/D-term RMS、油门和电机饱和信息。
- **先过安全门**：没有稳定飞行窗口、日志被撞击/失控保护占满、固件不在验证范围内时，不强行生成调参命令。
- **关注 RPM 证据**：不会仅凭 `dshot_bidir=ON` 就声称 RPM 滤波已经生效；需要活动电机 eRPM 或调试相关性支持。
- **渐进式调整**：优先给出一组可解释的阶段性改动，保留 I 项和前馈，避免用错误的“电机输出限制”掩盖 PID 问题。
- **适合复盘**：同时产出 `analysis.json` 与 `recommended_cli.txt`，方便保存、比较和回滚。

## 快速开始

将本仓库中的 `tune-betaflight-pid/` 复制到 Codex skills 目录，然后在 Codex 中调用：

```text
Use $tune-betaflight-pid to analyze this Betaflight .bbl and produce a staged CLI.
```

本 Skill 适用于 Betaflight 4.4/4.5 多旋翼。分析器需要 Python、NumPy，以及可用的 `blackbox_decode`；如果已经有解码后的 CSV，则不需要解码器。

## 命令行分析

```bash
cd tune-betaflight-pid
python scripts/analyze_bbl.py flight.bbl \
  --decoder /absolute/path/to/blackbox_decode \
  --output-dir /absolute/path/to/analysis
```

用基线日志做匹配窗口对比：

```bash
cd tune-betaflight-pid
python scripts/analyze_bbl.py new-flight.bbl \
  --baseline previous-flight.bbl \
  --decoder /absolute/path/to/blackbox_decode \
  --output-dir /absolute/path/to/analysis
```

先阅读 `analysis.json`，再复制 `recommended_cli.txt`。提交 CLI 前请保存飞控备份：

```text
diff all
```

配置工作时拆除桨叶；实际测试使用状态良好的桨叶，并一次只改变一类参数。

## 输出内容

| 文件 | 用途 |
| --- | --- |
| `analysis.json` | 日志来源、配置快照、质量门槛、频谱、RPM 证据、事件和调参决定 |
| `recommended_cli.txt` | 带注释的阶段性 CLI；通过硬门槛时才以 `save` 结束 |

重点报告包括：

- 固件/飞控/机体与有效日志时长
- RPM 遥测：已确认、仅配置或缺失
- 40–400 Hz 滤波陀螺仪与 D-term RMS
- 电机饱和比例、油门窗口和排除的撞击/降落事件
- 有基线时的同窗口前后变化
- 每个参数的改动理由、下一次测试的中止条件

## 安全边界

请勿在未装桨的 ARM 测试中判断最终 PID；电机页是开环测试，不能代表真实的姿态反馈回路。只有在 ESC 支持且电机极数正确时，才允许启用双向 DShot。出现异常声响、明显发热、持续振荡或控制失效时立即降落并断电。

更多调参规则见 [`references/decision-rules.md`](tune-betaflight-pid/references/decision-rules.md) 和 [`references/cli-rules.md`](tune-betaflight-pid/references/cli-rules.md)。

## 参与与支持

如果这个 Skill 帮你更快定位共振、验证 RPM 滤波或减少电机发热，欢迎给仓库点一个 **Star**，并分享你的 Betaflight 版本、日志质量和验证结果：

<https://github.com/pokrc/tune-betaflight-pid>

Issue/PR 建议附上脱敏后的结论、固件版本和复现步骤；不要上传遥控器绑定信息、个人凭据或 GitHub Token。

## 许可与署名

本项目采用 [PolyForm Noncommercial 1.0.0](LICENSE.md)。未经另行书面许可，禁止商业使用。再发布时必须保留 [`NOTICE.md`](NOTICE.md) 和 Skill 内的署名配置；生成的分享模式输出会保留固定署名：

`© POK_RC YAO — 版权所有；使用、转发请保留本署名。`

本项目独立于 Betaflight 与 Blackbox Tools，不主张其代码或商标权利。
