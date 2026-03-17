# 语音助手外放可打断方案设计文档  
## 面向场景：支持语音输入、支持用户打断、避免被自身外放误打断

---

# 1. 问题陈述

在语音助手场景中，系统需要同时满足以下目标：

1. **支持外放播报 TTS**
2. **支持用户在播报过程中自然打断（barge-in）**
3. **不被自身外放的声音误判为用户语音**
4. **在真实设备和复杂声学环境下保持稳定性**

这是一个典型的“外放 + 语音输入 + 可打断”问题，本质上涉及：

- 扬声器播放的人声重新进入麦克风
- VAD 误把回灌的 TTS 当成用户说话
- 用户和系统同时发声时的双讲（double-talk）
- AEC、VAD、状态机和 ASR/语义层之间的协同设计

---

# 2. 核心结论

## 2.1 单靠 VAD 不能解决问题

无论是 Silero VAD、WebRTC VAD 还是其他 VAD，本质上都只是回答：

> 当前音频里是否存在语音？

它们并不天然具备下面这个能力：

> 当前检测到的语音，是用户本人在说话，还是扬声器外放回灌进麦克风的语音？

因此：

- **Silero VAD 可以使用**
- 但 **Silero VAD 不能单独解决外放误打断问题**
- 外放场景下必须引入 **AEC（声学回声消除）**
- 并且需要有 **状态机 + 声学判定 + 语义复核**

---

## 2.2 正确的总链路

标准链路如下：

```text
播放参考流(Render) ───────────────┐
                                  ↓
Mic Capture → AEC3 → NS → VAD(Silero) → 声学打断判定 → 暂停TTS
                                                      ↓
                                                 ASR/语义复核
                                                      ↓
                                    真打断：进入对话     误打断：恢复TTS
```

简化表述：

```text
Mic → AEC → NS → VAD → 决策
```

绝对不建议：

```text
Mic → VAD → AEC
```

否则 VAD 会直接被系统自己的外放语音“锁死”。

---

# 3. 设计目标

本方案希望达到以下能力：

## 3.1 目标能力
- 外放播报时，系统不会轻易被自己声音误打断
- 用户一开口，可以快速触发打断
- 对咳嗽、噪声、嗯啊等无意义声音不敏感
- 对短暂残余回声不敏感
- 误触发后允许快速 rollback 恢复 TTS

## 3.2 非目标
- 不要求纯声学层 100% 区分“用户语音”和“回声”
- 不依赖某一个单独特征（如互相关）完成最终判断
- 不假设 AEC 能做到完全消除所有回声

---

# 4. 系统总方案

---

## 4.1 模块划分

系统分为四层：

### 第一层：播放层
- TTS 生成 PCM
- PCM 送往扬声器播放
- PCM 同时作为 render reference 输入给 AEC

### 第二层：采集与增强层
- 麦克风采集 PCM
- 经过 AEC3
- 经过 NS
- 可选轻量 AGC 或不使用 AGC
- 输出给 VAD

### 第三层：声学判定层
- 使用 Silero VAD 输出语音概率
- 结合 AEC 后残差能量、持续时长、滑窗命中率
- 判断是否进入“疑似打断”

### 第四层：语义确认层
- 暂停 TTS
- 抓取短时音频送轻量 ASR 或关键词识别
- 判断是否为真实打断
- 如果不是，执行 rollback，恢复 TTS

---

## 4.2 推荐最终架构

```text
TTS PCM → 扬声器播放
      └→ render_reference_buffer ───────────────┐
                                                ↓
Mic PCM → WebRTC AEC3 → NS → AGC(可选轻量) → Silero VAD
                                            ↓
                         residual energy / duration / sliding window
                                            ↓
                                   candidate interrupt
                                            ↓
                                         pause TTS
                                            ↓
                                 fast ASR / semantic verify
                                            ↓
                              true barge-in / rollback resume
```

---

# 5. 各模块职责说明

---

## 5.1 AEC（声学回声消除）

### 作用
AEC 的目标是从麦克风信号中减去由扬声器播放导致的回声成分。

### 为什么必须有
在外放场景中，麦克风收到的信号通常包含：

```text
Mic = 用户近讲语音 + 外放回声 + 环境噪声
```

如果没有 AEC，VAD 看到的是完整的人声混合体，几乎无法判断“这是用户还是系统自身播报”。

### 结论
- 外放场景下 AEC 是刚需
- 推荐使用 **WebRTC AEC3**

---

## 5.2 NS（降噪）

### 作用
- 压制环境噪声
- 降低 AEC 后残余噪声对 VAD 的干扰
- 提升后续 VAD 和 ASR 的稳定性

### 结论
- 强烈建议保留
- 放在 AEC 后面

---

## 5.3 VAD（Silero VAD）

### 作用
- 检测当前音频段是否含有语音
- 为打断判定提供“speech probability”

### 推荐理由
Silero VAD 具备以下优点：
- 概率输出而不是纯布尔
- 可结合阈值和时长后处理
- 对实际语音段检测比较友好
- 适合在 AEC/NS 后使用

### 注意
- VAD 不是回声分类器
- 不要让 `VAD = True` 直接等于“执行打断”

---

## 5.4 语义复核

### 作用
- 解决纯声学层误触发问题
- 判断暂停后的声音究竟是不是用户真的要打断

### 典型判断对象
#### 真打断
- “停”
- “等一下”
- “不是”
- 唤醒词
- 明确的新问题开头

#### 误触发
- 咳嗽
- 呼气
- “啊”“哦”“嗯”
- 和当前播报文本高度相似的残余回声内容

### 结论
语义层不是替代声学层，而是用于：
- 快速确认
- 回滚恢复
- 拉高系统上限

---

# 6. 关键工程原则

---

## 6.1 原则一：不要让单一特征决定打断

不建议把以下任一项作为唯一判定依据：

- 单帧 VAD
- 原始麦克风能量
- 单次峰值
- 残差与参考流的简单互相关

推荐做法是：**多特征组合 + 滑窗 + 状态机**

---

## 6.2 原则二：不要把 `corr_ref` 当主判据

### 背景
有人会尝试比较：
- AEC 后残差信号
- 当前播放参考流

如果两者“不像”，就认为是用户说话。

### 风险
这个思路在工程上不够稳，因为残余回声往往来自：

- 扬声器非线性失真
- 机壳共振
- 房间反射
- 声学路径变化
- 破音

这些成分本来就可能和原参考流低相关，因此：

> “低相关”并不等于“是用户语音”

### 结论
- `corr_ref` 最多作为弱特征
- **不要当主判据**
- 主判据应使用：
  - VAD 概率
  - AEC 后残差能量
  - 持续时长
  - 滑窗命中率
  - 语义复核结果

---

## 6.3 原则三：render reference 的时间对齐是成败关键

### 正确做法
AEC 输入的参考流必须尽量接近真实送往扬声器的最终 PCM。

### 风险来源
以下情况容易导致 AEC 性能急剧下降：

- 应用层多级缓冲
- 音频栈延迟抖动
- 蓝牙链路动态延迟
- USB 声卡
- 采样率不一致
- 中途重采样
- 音频设备切换

### 结论
- 优先拿“真正播放到设备的 PCM”
- 优先保证稳定时间基
- 必要时实现 delay estimation / delay compensation
- 设备切换后重新校准

---

## 6.4 原则四：AGC 要保守

AGC 如果太激进，可能会把残余回声重新放大，反而导致误触发。

建议：
- 不开 AGC
- 或仅保留轻量增益控制
- 不要在 TTS 播放期间 aggressively 拉高麦克风增益

---

## 6.5 原则五：TTS 最大音量要限制

外放音量越大：
- 回灌越强
- 非线性失真越重
- AEC 压力越大
- 残余回声越明显
- 误打断越多

因此应限制播报最大音量，尤其是在小体积设备或单麦方案下。

---

# 7. 最终状态机设计

---

## 7.1 状态定义

### S0：IDLE（空闲监听）
- 没有 TTS 播报
- 正常监听用户语音

### S1：TTS_PLAYING（TTS 播放中）
- 系统正在外放播报
- 麦克风仍在监听
- AEC 正在使用 render reference
- 使用更严格的打断门限

### S2：INTERRUPT_CANDIDATE（疑似打断）
- 声学层初步认为“可能用户开口了”
- 仍未真正进入用户输入

### S3：INTERRUPT_CONFIRM（暂停播报，短暂确认）
- 先暂停 TTS
- 抓取短时确认音频
- 用轻量 ASR / 关键词 / 语义做确认

### S4A：LISTENING（确认真打断，进入用户输入）
- 正式停止 TTS
- 进入用户说话状态
- 音频送正式 ASR

### S4B：ROLLBACK（误打断恢复）
- 判断不是有效打断
- 恢复 TTS 播放
- 返回 TTS_PLAYING

---

## 7.2 状态流转图

```text
IDLE
 └─(检测到用户语音)→ LISTENING
LISTENING
 └─(用户说完，系统开始播报)→ TTS_PLAYING
TTS_PLAYING
 └─(候选打断成立)→ INTERRUPT_CONFIRM
INTERRUPT_CONFIRM
 ├─(语义确认是真打断)→ LISTENING
 └─(语义确认是误打断)→ TTS_PLAYING
```

---

# 8. 声学层打断判定逻辑

---

## 8.1 主要特征

### 特征 A：Silero VAD 概率
记为：

```text
vad_prob
```

### 特征 B：AEC 后残差能量
记为：

```text
aec_residual_rms
```

### 特征 C：持续时长
记为：

```text
duration_ms
```

### 特征 D：滑窗命中率
记为：

```text
window_hit_ratio
```

### 可选特征 E：AEC 质量指标
如果接入层可以拿到：
- ERL
- ERLE
- residual echo 指标

则可辅助动态调参，但不强依赖。

---

## 8.2 推荐候选打断公式

```text
candidate_interrupt =
    (vad_prob > T_vad_tts)
AND (aec_residual_rms > T_residual)
AND (window_hit_ratio > T_hit)
AND (duration_ms > T_dur)
```

---

## 8.3 推荐初始参数

以下参数仅作为起始调参基线：

### IDLE 状态
- `T_vad_idle`：较灵敏
- 最短语音：120～180ms
- 最短静音：100～150ms

### TTS_PLAYING 状态
- `T_vad_tts`：比 IDLE 明显更高
- `T_dur`：180～300ms
- 窗口长度：300ms
- `T_hit`：0.7～0.8

### CONFIRM 状态
- 确认音频长度：300～600ms
- 在超时时间内未形成有效内容则 rollback

---

## 8.4 滑窗优先于单次连续计数

建议：

- 帧长：30ms
- 窗口长度：300ms
- 窗口内 10 帧中至少 8 帧命中才成立

这样比简单“连续超过 200ms”更稳，因为它对瞬时残差脉冲和双讲瞬态更不敏感。

---

# 9. 语义层设计

---

## 9.1 为什么需要语义层

纯声学层无法完全区分：
- 用户开口
- 咳嗽
- 短促噪声
- 无意义语气词
- 回灌残余

因此声学层的职责应该是：

> 先快速让系统停一下，看看是不是有人真的要打断

而不是直接永久停止当前 TTS。

---

## 9.2 推荐确认流程

### 步骤一：暂停 TTS
不是彻底销毁 TTS 状态，只是先暂停。

### 步骤二：收集确认音频
采集 300～600ms 音频。

### 步骤三：执行轻量 ASR 或关键词识别
判断以下情况：

#### 认为是真打断
- 打断词
- 唤醒词
- 明确意图词
- 明显用户查询开头

#### 认为是误打断
- “啊”“哦”“嗯”
- 咳嗽、呼气、轻噪声
- 与当前播报文本高度重合的内容

### 步骤四：决策
- 真打断：停止 TTS，切正式 ASR
- 误打断：恢复 TTS

---

## 9.3 关键词优先模式（可选）
如果希望更稳，可以设计成：

- 长播报期间只接受“打断词/唤醒词”
- 短播报期间允许任意明显语音打断

这是一个非常现实的工程折中。

---

## 9.4 语义回声拦截（推荐）
如果确认阶段的 ASR 结果和当前 TTS 正在播报的文本高度相似，则大概率是系统自己的残余播报，而不是用户说话。

这比做信号级互相关更稳健。

---

# 10. 状态重置（State Reset）设计

这是本方案非常关键的一部分。

---

## 10.1 为什么必须做状态重置

真实工程里，状态机不仅要有“状态流转”，还必须定义：

> 进入/退出某个状态时，哪些缓存、计数器、临时结果需要清空或重置。

否则会产生“历史脏数据污染下一轮”的问题。

典型后果包括：

- 上一轮滑窗命中残留，导致下一轮刚开始就误打断
- 上一次确认音频混入下一轮 ASR
- rollback 后立刻再次误触发
- 候选打断持续时长累计穿透到下一轮
- TTS 恢复后瞬间再次被历史数据触发停止

---

## 10.2 哪些属于必须重置的“业务状态”

以下内容通常必须在状态切换时按规则清理：

### A. 滑窗缓存
例如：
- 最近 N 帧 hit/miss 结果
- `window_hit_ratio`
- 连续命中计数

### B. 确认音频缓存
例如：
- `confirm_audio_buffer`

### C. 候选打断计数器
例如：
- `candidate_duration_ms`
- `speech_run_length`
- `residual_hit_frames`

### D. 临时文本与 ASR 结果
例如：
- `confirm_text`
- `partial_asr_result`

### E. rollback 临时标记
例如：
- `rollback_pending`
- `resume_position_valid`

---

## 10.3 哪些状态不应随意硬清空

以下内容属于信号处理器或模型的长期自适应状态，通常不应在每次状态切换时强制清零：

- AEC 自适应滤波器状态
- NS 内部状态
- VAD 模型的流式上下文状态

因为如果在每次切状态时都强行重置它们，可能导致：

- AEC 丢失已学习的 echo path
- 恢复播放后的前几百毫秒效果明显变差
- 系统频繁出现“热启动抖动”

### 正确原则
- **业务层短时缓存：状态切换时按规则清空**
- **DSP/模型内部长期状态：仅在链路根本变化时谨慎重置**

---

## 10.4 什么时候需要重置 DSP/模型长期状态

以下情况才考虑重置长期状态：

- 音频设备切换
- 采样率变化
- render reference 中断并重建
- 会话整体重启
- 长时间停止后重新开始
- 音频链路中断/恢复

---

## 10.5 状态重置矩阵

---

### 进入 `TTS_PLAYING`
#### 重置
- 候选滑窗缓存
- 候选计数器
- 连续命中计数
- confirm buffer
- confirm text
- residual 持续计数

#### 保留
- AEC 内部状态（通常保留）
- NS 内部状态（通常保留）
- VAD 内部上下文（通常保留）

---

### `TTS_PLAYING -> INTERRUPT_CONFIRM`
#### 动作
- 暂停 TTS
- 清空 confirm buffer
- 清空 confirm text
- 开始新的确认音频收集窗口

#### 重置
- confirm 收集计时器
- confirm 相关临时统计

---

### `INTERRUPT_CONFIRM -> TTS_PLAYING`（误打断 rollback）
#### 必须重置
- confirm buffer
- confirm text
- 候选滑窗
- `window_hit_ratio`
- 连续命中计数
- `candidate_duration_ms`
- residual 持续计数
- rollback 临时标记

#### 原因
这是最容易漏掉的一步。如果不清理，恢复 TTS 后会立刻再次被误打断。

---

### `INTERRUPT_CONFIRM -> LISTENING`（确认真打断）
#### 必须重置
- 候选打断所有临时统计
- confirm 相关缓存
- rollback 恢复点标记置无效
- TTS 恢复位置标记置无效

#### 说明
如果 confirm buffer 被移交给正式 ASR，需要在移交后清空本地缓存。

---

### `LISTENING -> IDLE`
#### 重置
- 用户本轮临时语音统计
- silence/run-length 计数器
- partial ASR 片段
- 本轮对话临时上下文（若有）

---

### 回到 `IDLE`
#### 建议清空全部业务层短时缓存
- 滑窗
- confirm buffer
- 候选计数器
- rollback 标记
- 本轮短时文本
- 短时统计量

---

## 10.6 一句工程原则

可以把下面这句话直接写进设计文档：

> 所有用于决策的短时缓存和计数器，都必须在状态迁移时按规则重置；只有信号处理器的长期自适应状态，才应谨慎保留。

---

# 11. 最容易踩的坑

---

## 11.1 AEC 参考流与实际播放流不同步
后果：
- AEC 效果急剧变差
- 残余回声变大
- VAD 和打断判定一起崩

---

## 11.2 恢复 TTS 后立即再次触发打断
常见原因：
- rollback 后没清滑窗
- confirm buffer 没清
- `candidate_duration_ms` 没清零
- residual hit 状态残留

---

## 11.3 过于依赖单一特征
例如：
- 只看 VAD
- 只看残差能量
- 只看互相关

后果：
- 误触发率高
- 在不同设备上极不稳定

---

## 11.4 AGC 过猛
后果：
- 残余回声被重新抬高
- 播报期间假打断变多

---

## 11.5 TTS 音量过大
后果：
- 扬声器失真增大
- 回声残差更重
- AEC 压力更高

---

## 11.6 设备切换后未重新校准
例如：
- 从内放切到蓝牙
- 从手机扬声器切到 USB 设备

后果：
- 延迟模型失效
- 旧状态污染新链路

---

# 12. 最终推荐版本

---

## 12.1 必选模块
- WebRTC AEC3
- NS
- Silero VAD
- 状态机
- 滑窗判定
- 状态重置机制

---

## 12.2 强烈推荐模块
- 暂停式候选打断
- 轻量 ASR / 关键词确认
- rollback 恢复 TTS
- 不同状态不同阈值
- 状态重置矩阵

---

## 12.3 可选增强
- 打断词优先模式
- 语义回声拦截
- 动态设备参数表
- AEC 指标驱动的自适应门限
- 波束形成 / 麦克风阵列增强

---

# 13. 推荐伪代码

```python
state = "IDLE"

candidate_window = []
confirm_audio_buffer = []
confirm_text = ""
candidate_duration_ms = 0
rollback_pending = False

def reset_candidate_state():
    global candidate_window, candidate_duration_ms
    candidate_window = []
    candidate_duration_ms = 0

def reset_confirm_state():
    global confirm_audio_buffer, confirm_text, rollback_pending
    confirm_audio_buffer = []
    confirm_text = ""
    rollback_pending = False

def enter_tts_playing():
    reset_candidate_state()
    reset_confirm_state()

def enter_interrupt_confirm():
    reset_confirm_state()

def rollback_to_tts():
    reset_candidate_state()
    reset_confirm_state()

def enter_listening_from_confirm():
    reset_candidate_state()
    reset_confirm_state()

while True:
    render_frame = get_current_tts_playback_frame()   # 若无播放则为 None
    mic_frame = read_mic_frame()

    aec_out = aec3.process(mic_frame, render_frame)
    ns_out = noise_suppress(aec_out)

    vad_prob = silero_vad(ns_out)
    residual_rms = calc_rms(ns_out)

    if state == "IDLE":
        if vad_prob > VAD_IDLE_TH and enough_duration():
            start_asr()
            state = "LISTENING"

    elif state == "TTS_PLAYING":
        hit = (
            vad_prob > VAD_TTS_TH and
            residual_rms > RESIDUAL_TH
        )

        update_candidate_window(candidate_window, hit)
        update_candidate_duration(hit)

        if sliding_window_hit_ratio(candidate_window) > HIT_RATIO_TH and duration_ok():
            pause_tts()
            enter_interrupt_confirm()
            state = "INTERRUPT_CONFIRM"

    elif state == "INTERRUPT_CONFIRM":
        confirm_audio_buffer.append(ns_out)

        if confirm_audio_ready(confirm_audio_buffer):
            text = fast_asr(confirm_audio_buffer)
            confirm_text = text

            if is_meaningful_barge_in(text):
                stop_tts()
                enter_listening_from_confirm()
                start_full_asr_with_prefill(confirm_audio_buffer)
                state = "LISTENING"
            else:
                resume_tts()
                rollback_to_tts()
                state = "TTS_PLAYING"

    elif state == "LISTENING":
        if user_speech_finished():
            run_nlu()

            if should_start_tts():
                start_tts()
                enter_tts_playing()
                state = "TTS_PLAYING"
            else:
                reset_candidate_state()
                reset_confirm_state()
                state = "IDLE"
```

---

# 14. 一句话总结

本方案的核心思想是：

> 用 AEC3 先压制系统自身外放回声，用 Silero VAD 检测处理后的语音活动，用滑窗和持续时长做稳健的声学候选判定，再用语义层确认是否真的打断，并在状态迁移时严格执行缓存和计数器重置，防止历史脏数据污染下一轮决策。

---

# 15. 最终结论

对于“语音助手支持外放、支持用户打断、但不希望被自己外放误打断”的场景，推荐的完整方案是：

1. **必须使用 AEC**
2. **VAD 放在 AEC/NS 后**
3. **不让单一 VAD 命中直接触发打断**
4. **采用滑窗 + 残差能量 + 时长的声学判定**
5. **采用暂停式确认而非直接永久停止**
6. **通过轻量 ASR/关键词进行语义复核**
7. **支持 rollback 恢复 TTS**
8. **为所有业务短时缓存设计严格的状态重置规则**

这是一个面向真实工程落地、稳定性优先、同时兼顾用户自然打断体验的修正版方案。

---