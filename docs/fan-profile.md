# fan-profile — 风扇/散热策略统一控制

跨厂商的风扇策略控制框架（UI 层在 chezmoi：rofi 菜单 + eww power-popup 风扇区）。

## 架构

```
/usr/local/lib/fan-profile/
├── fan-profile        # 主 CLI（唯一入口；/usr/local/bin 有符号链接）
├── lib/common.sh      # hwmon 扫描、JSON 输出、档位归一化
└── adapters/          # 每机器一个适配器，按探测顺序降级
    ├── acpi-platform-profile   # /sys/firmware/acpi/platform_profile（跨厂商标准）
    ├── asus-throttle           # 旧 ASUS：throttle_thermal_policy (0/1/2)
    ├── thinkpad-fan            # 旧 ThinkPad：/proc/acpi/ibm/fan level
    ├── hwmon-pwm               # 台式机：pwm 自动模式（v1 仅 balanced）
    └── readonly                # 兜底：只读（风扇/温度仍可查）
```

**适配器契约**（每个适配器是可执行脚本，接五个子命令）：

| 命令 | 行为 |
|---|---|
| `detect` | exit 0 = 本机适用 |
| `choices` | 本机档位（canonical 词汇：quiet/balanced/performance + 厂商原名） |
| `get` | 当前档位（native 名） |
| `set <档位>` | 应用（校验输入；失败 exit≠0 + stderr 原因） |
| `status` | 风扇/温度 JSON 片段（可省略，默认走公共 hwmon 扫描） |

**档位归一化**：`normalize()` 把厂商别名映射到 canonical（low-power/power-saver→quiet、overboost→performance 等）。UI 只消费 canonical。

## CLI

```bash
fan-profile status              # JSON 单行：backend/supported/current/choices/fans/temp_c
fan-profile choices             # 档位列表（保序去重）
fan-profile get                 # 当前档位
fan-profile set <档位>           # 切换（root；sudoers NOPASSWD 授权给 target_user）
fan-profile probe               # 探测后端并输出名字（缓存于 /run/fan-profile/）
fan-profile default [档位]       # 读/写 /etc/fan-profile/default
fan-profile apply-default       # 应用开机默认（boot 单元）
fan-profile apply-resume        # 恢复上次应用值（resume 单元；/run 缓存丢失时回落默认）
```

探测结果缓存于 `/run/fan-profile/backend`（tmpfs，重启失效），rofi/eww/systemd 共享一次探测。

## systemd

- `fan-profile.service`（multi-user.target，oneshot）：开机应用 `/etc/fan-profile/default`（默认 `quiet`）——EC 重启后回落 0（均衡），必须由它扳回。
- `fan-profile-resume.service`（suspend/hibernate/hybrid-sleep）：恢复 `/run/fan-profile/last` 记录的上次档位（部分机型 EC 休眠会重置策略）。

## 权限

`/etc/sudoers.d/fan-profile`：`<user> ALL=(root) NOPASSWD: /usr/local/lib/fan-profile/fan-profile`
——sudoers 只放开该脚本路径，脚本内部对所有子命令/参数做白名单校验。读路径全部 world-readable，无需 root。

## 实测验证（Vivobook N7600ZE, 2026-08-11）

- 三档映射：`quiet→platform_profile=quiet, throttle_thermal_policy=2`；`balanced→0`；`performance→1`
- 负载实测（8 线程）：性能档风扇最激进 ~3100 RPM / CPU 峰值 ~79°C；静音档风扇钉 2300 RPM 下限、CPU 被功耗墙限制（稳定 ~61°C）；均衡居中
- eww seg-btn 点击、rofi 选择、boot 服务重应用、readonly 兜底契约均通过

## 已知约束

- 本机静音档风扇仍有 2300 RPM 下限（该型号 EC 无停转设计）
- hwmon-pwm 适配器 v1 只支持 `balanced`（自动）；自定义曲线属于 fancontrol 守护进程，超出本框架范围
- 12 代 Intel 锁了 undervolt，别用 intel-undervolt 间接降热
