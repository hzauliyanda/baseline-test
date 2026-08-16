# baseline-test kit —— 测试基线四步管道

给测试同学的全链路工具包：把一个系统模块从「没测过」带到「每次回归一键出报告 + 审查收口」。
Claude Code 和 Codex 都能用同一套，产物一样、门一样。

## 解决什么问题

真事：创建工单有 4 个类型，AI 生成的用例只走了 1 个类型——没人发现，直到上线后漏测的类型出事。
本 kit 用**枚举维度表 + 机算放行门**堵这类洞：每个 endpoint / 交互 / 枚举值，要么有真用例，
要么显式 exempt 带理由，缺一个都不放行。

## 四步

```
① tc-explore  探索建基线   双源扫描（前后端 git）+ ego 页面遍历 → 功能地图 + baseline.yaml + flow 初版
② tc-cases    用例派生     功能/UI/API 用例 + 覆盖对账，check_coverage.py 放行门（缺口全列名）
③ tc-run      执行回归     run_regression.py 一键 API+UI+报告 HTML，末尾对账基线口径
④ tc-verify   审查收口     机算六项 + 干净上下文五项对账，verdict 落盘——无 verdict 不得宣称完成
```

管道铁律：上一步产物 = 下一步输入；②不 Green 不进③；④无 verdict 不算完。
**回填循环**：遗漏是常态，三层循环（门内循环/首跑回填/漂移审计 `--diff`）消化，产物只累加不重写——详见 `docs/SOP-四步.md`。

## 安装

Claude Code 和 Codex 都支持 skill（同一套 agentskills 标准，SKILL.md 同格式），
区别只在 skill 目录：`~/.claude/skills/` vs `~/.codex/skills/`。
按你用的工具二选一，**整段复制贴给它**，装完它会回你结果。

**Claude Code 用户**（装 4 个薄壳 skill，之后说「跑回归」「审查收口」就能触发）：

```
帮我安装 baseline-test kit，逐步执行下面四条命令并回我每步结果：
1. git clone <kit仓地址> ~/baseline-test
2. mkdir -p ~/.claude/skills
3. cp -r ~/baseline-test/skills/tc-* ~/.claude/skills/
4. perl -pi -e 's|<kit根>|$ENV{HOME}/baseline-test|g' ~/.claude/skills/tc-*/SKILL.md
（第 4 步把薄壳里的 <kit根> 占位符替换为实际克隆路径；装到别的路径就把 1 和 4 里的路径一起换）
```

**Codex 用户**（同样装 4 个薄壳 skill，只是目录不同）：

```
帮我安装 baseline-test kit，逐步执行下面四条命令并回我每步结果：
1. git clone <kit仓地址> ~/baseline-test
2. mkdir -p ~/.codex/skills
3. cp -r ~/baseline-test/skills/tc-* ~/.codex/skills/
4. perl -pi -e 's|<kit根>|$ENV{HOME}/baseline-test|g' ~/.codex/skills/tc-*/SKILL.md
（第 4 步把薄壳里的 <kit根> 占位符替换为实际克隆路径；装到别的路径就把 1 和 4 里的路径一起换。
 装完开新会话才会发现 skill；没被发现就重启会话再试）
```

两边的薄壳内容一样，都只是指向 `docs/SOP-四步.md` 的触发壳——不装 skill 也行，
直接对 AI 说「读 ~/baseline-test/docs/SOP-四步.md，按我所在的步骤干活」。

## 5 分钟上手（拿一个真实模块）

```bash
# 1. 脚手架（前后端仓在本地的话，git 地址和审计 commit 自动填）
~/baseline-test/steps/1-explore/new-module.sh ~/tc-modules/<系统>/<模块> \
    --backend ~/code/后端仓 --frontend ~/code/前端仓 --title 模块中文名

# 2. 双源扫描（出 endpoint/枚举/路由 三份 draft）
python3 ~/baseline-test/steps/1-explore/scan_repos.py ~/tc-modules/<系统>/<模块> \
    --api-prefix /mapi/你的模块 --frontend-key 路由关键词

# 3. 之后对你的 AI 说：
#    「读 ~/baseline-test/docs/SOP-四步.md，模块在 ~/tc-modules/<系统>/<模块>，从①的 ego 页面遍历继续」
```

金标准参考：`examples/risk-normal-work-order/`（真实模块全链路产物，含 verdict 审查实录）。

## 目录约定（铁律：kit ≠ 数据）

| 目录 | 角色 | 性质 |
|---|---|---|
| `~/baseline-test/` | kit 本体（脚本 / SOP / skill 薄壳），`git pull` 即升级 | 工具仓 |
| `~/tc-modules/<系统>/<模块>/` | 模块基线包（baseline.yaml / 用例 / coverage / explore draft） | 测试资产仓 |

- **模块数据绝不放进 kit 仓**——kit 升级 `git pull`、数据沉淀互不干扰
- 发现规则零配置：工作区下任何 `*/*/baseline.yaml` = 一个模块，建目录即登记
- 建议整个工作区 `~/tc-modules/` 做成**一个公司私有仓**（新模块 = 新目录）；
  capture/截图/报告 HTML 是敏感或每轮重生成的，脚手架的 `.gitignore` 已挡在库外
- 换根：`TC_MODULES=~/别处 python3 ~/baseline-test/kit-admin.py status`

**舰队视图**（模块多了以后的一览/巡检）：

```bash
python3 ~/baseline-test/kit-admin.py status
# 系统 | 模块 | 覆盖门 | verdict | 最近报告 | audit_base
#   覆盖门=check_coverage 实跑；audit_base=锚 vs 本地 HEAD（落后提示进①回填）
# exit 0=全部健康；1=有模块需关注（门未过 / verdict=FAIL）——可直接当巡检定时任务
```

## 依赖

- python3 ≥3.9 + `pyyaml`（`pip3 install pyyaml`）
- `git`（读代码仓做覆盖对账）
- **ego-browser**（①页面遍历、③UI 回归的浏览器通道；需已登录目标系统）
- 没有 ego-browser？API 段（①扫描/②API用例/③API回归/④）完整可用，UI 段等装好 ego 再补

## 目录地图

| 路径 | 是什么 | 给谁 |
|---|---|---|
| `docs/SOP-四步.md` | **主操作手册**（含回填循环） | 人 + 任何 AI |
| `SPEC.md` | 设计契约（冲突时以它为准） | 想改 kit 的人 |
| `steps/1..4-*/` | 每步的脚本 + README（逻辑都在这） | AI 执行时读 |
| `kit-admin.py` | 多模块舰队视图（`status`，glob 发现 + 覆盖门/verdict/漂移巡检） | 管多个模块的人 |
| `skills/tc-*` | 触发薄壳（20 行/个，装进 `~/.claude/skills/` 或 `~/.codex/skills/`） | Claude / Codex 用户 |
| `examples/risk-normal-work-order/` | 金标准实例 | 所有人对照 |
| `AGENTS.md` / `CLAUDE.md` | Codex / Claude 的仓库入口指针 | AI |

## 安全提醒

模块目录和 explore draft 含内网系统信息（endpoint/表名/枚举）——**模块仓和本 kit 仓都只进公司内网 git，不要推公开仓**。
