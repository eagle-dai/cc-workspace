# 文件名建议

`humanoid_robot_barge_in_design.md`

# 人形机器人外放可打断语音交互方案设计文档

## 面向场景：人形机器人支持外放播报、支持用户打断、避免被自身外放和机体噪声误打断

---

# 1. 问题背景

人形机器人通常需要同时具备以下能力：

1. **外放播报 TTS**
2. **持续监听用户语音输入**
3. **支持用户在机器人播报过程中随时打断**
4. **避免被自身外放声音误判为用户语音**
5. **避免被机器人自身机械噪声、电机噪声、风扇噪声、行走振动等误触发**

相比手机、智能音箱、耳机设备，人形机器人在声学上更复杂，因为它通常同时具备：

- 多个麦克风，形成麦克风阵列
- 一个或多个扬声器
- 机体腔体反射和共振
- 头部、胸腔、外壳带来的复杂声学路径
- 关节电机、底盘、电源风扇等机体噪声
- 行走、转头、挥手等运动引入的时变干扰
- 用户往往处于远场，而不是近讲场景
- 多人环境中可能存在多个说话人

因此，人形机器人上的“可打断语音交互”本质上不是单纯的 VAD 问题，而是一个多模块协同问题，涉及：

- AEC（声学回声消除）
- Beamforming（波束形成）
- NS（降噪）
- Dereverb（可选去混响）
- VAD（语音活动检测）
- 状态机
- 短时缓存与状态重置
- ASR/语义确认
- 机器人自身运动状态建模
- 声源方向信息利用

---

# 2. 问题定义

在机器人播报 TTS 时，麦克风收到的信号通常可以近似表示为：

```text
Mic = 用户语音 + 扬声器回声 + 环境噪声 + 机体噪声 + 房间反射
```

如果系统处理不当，会出现以下典型问题：

## 2.1 自身外放误打断

机器人自己正在播报，TTS 经扬声器播放后回灌到麦克风，VAD 误判为“用户正在说话”，导致机器人把自己打断。

## 2.2 机体噪声误打断

机器人在运动、转头或电机动作时，关节、电机、底盘、风扇等噪声被误当作人声触发。

## 2.3 用户真实打断不及时

如果为了防误触发而把门限设得过高，用户真正开口时机器人又无法及时停下播报。

## 2.4 rollback 缺失导致体验差

机器人一旦误判为打断就立刻终止 TTS，没有二次确认和恢复机制，会导致交互非常生硬。

## 2.5 状态污染导致反复误触发

如果状态切换时不清理滑窗、确认缓存、短时统计量，系统会被上一轮历史数据污染，出现重复误打断。

---

# 3. 设计目标

本方案面向人形机器人，目标如下：

## 3.1 核心目标

- 机器人外放播报时，尽量不被自身播报误打断
- 用户在机器人播报过程中开口时，可快速实现打断
- 对咳嗽、呼气、机械噪声、行走噪声、短时冲击噪声不敏感
- 支持误触发后的 rollback 恢复 TTS
- 支持多麦阵列和方向信息接入
- 支持机器人运动状态作为辅助门控条件
- 具备可工程化落地的状态机与 reset 机制

## 3.2 非目标

- 不追求单一模块解决全部问题
- 不假设 AEC 能完全消除所有回声
- 不假设纯声学层能 100% 区分“用户说话”和“自身残留”
- 不依赖单个阈值完成最终判断

---

# 4. 核心结论

## 4.1 单靠 VAD 不够

无论使用 Silero VAD、WebRTC VAD 还是其他 VAD，VAD 本质上回答的是：

> 当前音频里有没有语音活动

它不天然回答：

> 这个语音到底来自用户、来自机器人扬声器残留，还是来自某种复杂噪声

因此在人形机器人场景中：

- **VAD 必须有**
- **但 VAD 绝不能单独承担防误打断任务**
- 必须结合：
  - AEC
  - 波束形成 / 空间信息
  - 降噪
  - 状态机
  - 短时缓存重置
  - 语义复核

---

## 4.2 正确总链路

推荐的总链路如下：

```text
TTS Render ───────────────┐
                          ├─→ Speaker
                          └─→ AEC Reference

Mic Array
  ├─→ Beamforming / DOA / Spatial Features
  ├─→ AEC
  ├─→ NS / Dereverb
  ├─→ VAD
  └─→ Residual / Duration / Window Statistics

Robot Motion State
  ├─→ Head motion
  ├─→ Walking
  ├─→ Motor activity
  └─→ Fan / body noise state

Decision Layer
  = 声学特征 + 空间特征 + 机器人状态特征

Confirm Layer
  = pause TTS + fast ASR / keyword / semantic verification

Output
  = 真打断 / rollback 恢复 TTS
```

---

# 5. 整体架构设计

---

## 5.1 系统模块划分

整个系统建议分为六层：

### 第一层：播放层

- TTS 生成 PCM
- PCM 输出到扬声器
- 同时把最终播放 PCM 送给 AEC 作为 render reference

### 第二层：麦克风阵列层

- 采集多通道音频
- 做波束形成
- 做声源方向估计（DOA）
- 产生空间特征

### 第三层：增强层

- AEC
- NS
- 可选 Dereverb
- 可选保守 AGC

### 第四层：VAD 与候选判定层

- Silero VAD 或其他概率型 VAD
- 残差能量估计
- 滑窗统计
- 候选打断判定

### 第五层：机器人状态融合层

- 当前是否在走路
- 当前头部是否在运动
- 当前关节是否在高速动作
- 当前风扇 / 电机是否处于高负载状态
- 根据状态动态调整门限

### 第六层：确认与恢复层

- 暂停 TTS
- 抓取确认音频
- 做 fast ASR / 关键词识别 / 语义判断
- 真打断则进入用户输入
- 误打断则 rollback 恢复 TTS

---

## 5.2 推荐最终架构图

```text
TTS PCM
  ├─→ Speaker Playback
  └─→ Render Reference Buffer
            │
            ▼

Mic Array Input
  ├─→ Beamforming
  ├─→ DOA / Spatial Features
  └─→ Multi-channel preprocessing
            │
            ▼

AEC → NS → (Optional Dereverb) → VAD
            │
            ├─→ residual energy
            ├─→ duration statistics
            ├─→ sliding window hit ratio
            └─→ speech probability
                    │
                    ▼

Robot State Fusion
  ├─→ head motion state
  ├─→ walking state
  ├─→ motor/fan state
  └─→ speaker volume state
                    │
                    ▼

Acoustic Candidate Interrupt Decision
                    │
                    ▼

Pause TTS
  └─→ collect confirm audio
            │
            ▼

Fast ASR / Keyword / Semantic Verify
  ├─→ true barge-in → stop TTS → full ASR
  └─→ false trigger → rollback → resume TTS
```

---

# 6. 各模块职责

---

## 6.1 AEC（声学回声消除）

### 职责

消除扬声器播放内容经机器人机体、房间和空气传播后回灌到麦克风的成分。

### 为什么在人形机器人中更关键

机器人通常具有：

- 扬声器与麦克风共机体安装
- 更复杂的腔体反射
- 时变声学路径
- 头部转动导致的路径变化
- 远场外放音量偏大

因此 AEC 在机器人上的作用不是可选项，而是基础能力。

### 设计要求

- 必须输入**尽量接近真实播放链路末端的 PCM**
- 必须保证 render 与 capture 的时间对齐尽可能稳定
- 音频设备切换或链路变化后需要重新校准

---

## 6.2 Beamforming（波束形成）

### 职责

利用麦克风阵列增强某个方向上的信号，抑制非目标方向的噪声和干扰。

### 为什么机器人必须考虑它

人形机器人通常面对的是：

- 远场用户
- 多说话人环境
- 房间混响
- 侧向或后向噪声源
- 机体某些方向固定噪声

如果阵列能力可用，应尽量加入 Beamforming。

### 作用

- 提高目标说话人方向上的 SNR
- 降低非目标方向噪声
- 为“是否真打断”提供方向维度特征

---

## 6.3 DOA / 空间特征

### 可用空间信息

- 声音来自哪个方向
- 是否来自用户正前方
- 是否接近扬声器方向
- 是否更像机体内部噪声方向

### 应用方式

可作为“打断门控”辅助特征：

- 语音来自用户正前方，降低打断门限
- 语音来自扬声器方向，提升打断门限
- 方向分布异常或不稳定时，不轻易触发

---

## 6.4 NS（降噪）

### 职责

抑制环境噪声与部分机体底噪，减轻后续 VAD 和 ASR 的压力。

### 说明

NS 不能代替：

- AEC
- Beamforming
- 运动状态融合

但它是基础稳态增强模块，建议保留。

---

## 6.5 Dereverb（可选去混响）

如果机器人主要用于：

- 大厅
- 商场
- 展馆
- 空旷室内场景

则混响可能显著影响 VAD / ASR 和残差评估，建议增加 Dereverb 或至少保留接口。

---

## 6.6 VAD（建议使用概率型 VAD）

### 职责

判断当前处理后的音频是否存在语音活动。

### 推荐做法

- 将 VAD 放在 AEC / NS 之后
- 使用概率输出，而不是单纯布尔值
- 把 VAD 作为候选打断的一部分证据，而不是唯一证据

### 说明

Silero VAD 是合适候选，但它并不负责回声消除，也不负责机器人状态理解。

---

## 6.7 机器人状态融合

这是人形机器人方案相对普通设备最重要的增强项之一。

### 需要接入的状态

- 当前是否静止
- 当前是否行走
- 当前是否快速转头
- 当前是否有高负载关节动作
- 当前风扇是否高速运转
- 当前 TTS 音量等级

### 融合目的

让系统知道：

> 当前声学环境是否已经因为机器人自己动作而恶化

从而动态调整候选打断阈值。

---

## 6.8 语义确认层

### 职责

解决纯声学层不可避免的误触发。

### 核心思路

- 声学层先快速暂停 TTS
- 语义层确认是不是用户真正意图打断
- 若不是，则恢复 TTS

### 典型判定

#### 真打断

- “停一下”
- “等等”
- “不是”
- 机器人名字
- 明确的新问题开头

#### 误打断

- 咳嗽
- 呼气
- “啊”“哦”“嗯”
- 与当前播报文本高度相似的残余内容

---

# 7. 人形机器人专属工程原则

---

## 7.1 原则一：不要只依赖纯音频阈值

在人形机器人上，仅凭：

- 原始能量
- 单帧 VAD
- 单次峰值

都非常不稳。

必须综合：

- 声学特征
- 空间特征
- 机器人运动状态
- 语义确认结果

---

## 7.2 原则二：不要把信号级互相关当主判据

尝试直接比较：

- AEC 后残差
- 当前播放参考流

并用“是否相似”来判断是否是用户语音，这在机器人上尤其不稳。

原因包括：

- 扬声器非线性失真
- 机体共振
- 房间反射
- 机械耦合噪声
- 时变路径

因此：

- `corr_ref` 最多做弱特征
- 不作为硬判据

---

## 7.3 原则三：时间对齐是 AEC 成败关键

AEC 的 render reference 必须尽量接近真正扬声器播放流。

以下情况会显著恶化 AEC：

- 音频栈多级缓冲
- 蓝牙音频链路
- USB 音频设备
- 重采样
- 设备切换
- 头部或机体运动带来的路径变化

因此：

- 优先取最终播放 PCM
- 尽量统一采样率
- 做延迟估计与补偿
- 设备切换后重建链路状态

---

## 7.4 原则四：机器人自身运动必须进入门控逻辑

机器人在不同运动状态下，声学条件差异极大。

### 例子

- 静止不动时：可降低打断门限，提高灵敏度
- 行走时：提高打断门限
- 快速转头时：短时间 suppress 候选打断
- 关节高速动作时：临时冻结部分弱触发条件

---

## 7.5 原则五：方向信息值得强利用

如果说话方向：

- 接近用户所在方向
- 与机器人当前关注方向一致

则更可能是真打断。

如果方向：

- 接近扬声器方向
- 更像机体内部噪声方向

则应提高门限或不立即打断。

---

## 7.6 原则六：语义 rollback 是体验关键

没有 rollback 的机器人会表现得非常笨：

- 播到一半自己停住
- 被咳嗽打断
- 被路过噪声打断
- 被残余回声打断后无法恢复

因此建议始终支持：

- 暂停式确认
- rollback 恢复播放

---

# 8. 最终状态机设计

---

## 8.1 状态定义

### S0：IDLE

机器人空闲监听状态，没有在播报。

### S1：LISTENING

机器人确认用户正在说话，进入正式用户输入状态。

### S2：TTS_PLAYING

机器人正在外放播报，同时保持监听能力。

### S3：INTERRUPT_CANDIDATE

声学层认为“可能有人在打断”。

### S4：INTERRUPT_CONFIRM

先暂停 TTS，收集短时确认音频，等待语义确认。

### S5A：TRUE_BARGE_IN

确认是真打断，停止 TTS，转正式 ASR。

### S5B：ROLLBACK_RESUME

确认是误触发，恢复 TTS 播报。

---

## 8.2 状态流转图

```text
IDLE
 └─(检测到用户语音)→ LISTENING

LISTENING
 └─(用户说完，系统开始回复)→ TTS_PLAYING

TTS_PLAYING
 └─(候选打断成立)→ INTERRUPT_CONFIRM

INTERRUPT_CONFIRM
 ├─(确认是真打断)→ LISTENING
 └─(确认是误打断)→ TTS_PLAYING
```

---

# 9. 候选打断判定逻辑

---

## 9.1 使用的主要特征

### 声学特征

- `vad_prob`
- `aec_residual_rms`
- `duration_ms`
- `window_hit_ratio`

### 空间特征

- `doa_user_confidence`
- `is_front_direction`
- `is_near_speaker_direction`

### 机器人状态特征

- `is_walking`
- `is_head_moving_fast`
- `is_joint_noise_high`
- `is_fan_noise_high`

---

## 9.2 推荐候选打断公式

```text
candidate_interrupt =
    (vad_prob > T_vad_tts)
AND (aec_residual_rms > T_residual)
AND (window_hit_ratio > T_hit)
AND (duration_ms > T_dur)
AND spatial_gate_pass
AND motion_gate_pass
```

其中：

```text
spatial_gate_pass =
    用户方向置信度高
    或者
    当前方向不像扬声器方向

motion_gate_pass =
    当前不处于高风险机械噪声状态
    或在高风险状态下满足更严格阈值
```

---

## 9.3 推荐门限策略

### 静止 + 正前方用户

- 可以较灵敏
- 更容易触发候选打断

### 行走中

- 提高 `T_vad_tts`
- 提高 `T_residual`
- 提高 `T_hit`

### 快速转头中

- 短时提高门限
- 或冻结候选打断判定几百毫秒

### 关节高速动作中

- 仅允许明确打断词触发
- 或进入“强语义优先模式”

---

## 9.4 滑窗优先

建议：

- 帧长：20~30ms
- 滑窗长度：250~400ms
- 在窗口内命中率达到 70%~80% 才成立

不要使用单帧或单峰值直接触发。

---

# 10. 语义确认层设计

---

## 10.1 推荐流程

### 第一步：暂停 TTS

不是立刻销毁播放状态，而是先暂停。

### 第二步：抓取确认音频

收集 300~600ms 的确认音频。

### 第三步：快速确认

通过以下方式之一或组合：

- fast ASR
- 打断词识别
- 机器人名字识别
- 简单语义分类器

### 第四步：决策

#### 真打断

- 停止 TTS
- 进入 LISTENING
- 将确认音频作为 ASR 前缀输入

#### 误打断

- 恢复 TTS
- 回到 TTS_PLAYING

---

## 10.2 推荐真打断条件

例如：

- 检测到明确打断词
- 检测到唤醒词 / 机器人名字
- 识别结果表明用户开始发起新指令
- 连续语音长度足够且方向信息可信

---

## 10.3 推荐误触发条件

例如：

- 咳嗽
- 呼气
- “嗯”“啊”“哦”
- 与当前 TTS 文本高度相似
- 无明确语义
- 方向和机器人扬声器方向高度一致

---

## 10.4 语义回声拦截

如果 fast ASR 输出的文本与当前 TTS 正在播报的内容高度重合，则大概率是机器人自身残余播报，不应视为用户打断。

---

# 11. 状态重置（State Reset）设计

这是工程落地中非常关键的一部分。

---

## 11.1 为什么必须设计 reset 规则

状态机不仅要定义“怎么切状态”，还必须定义：

> 在进入/退出每个状态时，哪些短时缓存、计数器、临时变量、确认音频必须清空

否则会出现以下问题：

- 上一轮滑窗残留导致下一轮刚开始就误打断
- 确认音频混入下一轮 ASR
- rollback 后立即再次误触发
- 历史统计穿透到新一轮判定

---

## 11.2 必须重置的业务层短时状态

### A. 候选滑窗缓存

- hit/miss 序列
- hit ratio
- 连续命中计数

### B. 确认音频缓存

- `confirm_audio_buffer`

### C. 候选时长统计

- `candidate_duration_ms`
- `residual_hit_frames`

### D. 临时语义结果

- `confirm_text`
- `partial_asr_result`

### E. rollback 相关标记

- `rollback_pending`
- `resume_position_valid`

---

## 11.3 不应频繁硬清零的长期状态

以下状态通常不应在每次状态切换时硬重置：

- AEC 自适应状态
- NS 内部状态
- Beamforming 内部状态
- VAD 流式上下文

因为这会导致：

- AEC 丢失 echo path 学习结果
- 切换后前几百毫秒性能明显变差
- 系统出现频繁热启动抖动

---

## 11.4 什么时候才重置长期状态

- 音频设备切换
- 采样率变化
- render reference 中断/重建
- 机器人主音频链路重启
- 麦克风阵列拓扑变化
- 会话整体重启

---

## 11.5 状态重置矩阵

### 进入 `TTS_PLAYING`

#### 重置

- 候选滑窗
- 候选计数器
- confirm buffer
- confirm text
- residual 持续计数

#### 保留

- AEC 状态
- NS 状态
- Beamforming 状态
- VAD 状态

---

### `TTS_PLAYING -> INTERRUPT_CONFIRM`

#### 动作

- 暂停 TTS
- 清空 confirm buffer
- 清空 confirm text
- 启动新的确认窗口

---

### `INTERRUPT_CONFIRM -> TTS_PLAYING`

#### 必须重置

- confirm buffer
- confirm text
- 候选滑窗
- hit ratio
- 连续命中计数
- candidate duration
- residual 持续计数
- rollback 标记

#### 原因

这是最容易漏掉的一步，不清理的话，恢复 TTS 后会立即再次被误触发。

---

### `INTERRUPT_CONFIRM -> LISTENING`

#### 必须重置

- 候选判定相关临时统计
- confirm 缓存
- rollback 恢复点标记
- TTS 恢复位置标记失效

---

### 回到 `IDLE`

#### 建议清空全部业务层短时缓存

- 滑窗
- confirm buffer
- 临时文本
- 计数器
- rollback 标记
- 短时统计结果

---

## 11.6 一条工程原则

建议在文档中明确写出：

> 所有用于决策的短时缓存和计数器，都必须在状态迁移时按规则重置；只有信号处理器的长期自适应状态，才应谨慎保留。

---

# 12. 机器人场景下的参数策略

---

## 12.1 静止模式

适用于：

- 机器人静止站立
- 环境相对安静
- 用户在正前方

建议：

- 候选门限较低
- 打断更灵敏
- 更自然的交互体验

---

## 12.2 行走模式

适用于：

- 机器人正在移动
- 底盘、电机、惯性噪声更明显

建议：

- 提高 VAD 阈值
- 提高残差门限
- 增加确认窗口
- 必要时只允许打断词触发

---

## 12.3 转头/挥手/高速关节动作模式

适用于：

- 快速机械动作
- 机械噪声瞬时变化明显

建议：

- 短时间 suppress 候选打断
- 或者只接受高置信语义确认

---

## 12.4 高音量播报模式

适用于：

- 机器人在嘈杂场所主动提高音量

建议：

- 提高残差判定门限
- 强化 rollback
- 降低对短促语音的敏感度

---

# 13. 最容易踩的坑

---

## 13.1 只做 AEC + VAD，不接入机器人状态

结果：

- 机器人运动时大量误触发
- 不同动作模式下表现极不稳定

---

## 13.2 不使用阵列空间信息

结果：

- 无法区分用户方向和扬声器方向
- 多人场景误触发变多

---

## 13.3 rollback 后未清状态

结果：

- TTS 一恢复就再次被打断

---

## 13.4 设备切换或链路变化后未重校准

结果：

- AEC 失效
- 候选判定劣化

---

## 13.5 AGC 过强

结果：

- 机械噪声和残余回声被重新抬高

---

## 13.6 音量无限制

结果：

- 扬声器失真严重
- 机体共振严重
- 残差显著增大

---

# 14. 最终推荐版本

---

## 14.1 必选模块

- AEC
- Beamforming（若阵列可用）
- NS
- 概率型 VAD
- 候选打断状态机
- 状态重置机制
- 暂停式确认
- rollback 恢复

---

## 14.2 强烈推荐模块

- DOA / 空间特征
- 机器人运动状态门控
- fast ASR / 关键词确认
- 语义回声拦截
- 不同模式下的动态参数表

---

## 14.3 可选增强

- Dereverb
- 打断词优先模式
- 用户方向跟踪
- 视觉辅助确认
- 多说话人优先级管理

---

# 15. 参考伪代码

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

def get_robot_motion_gate():
    if is_head_moving_fast() or is_joint_noise_high():
        return "STRICT"
    if is_walking():
        return "MEDIUM"
    return "NORMAL"

def spatial_gate_pass(doa_info):
    if doa_info.is_front_user_direction:
        return True
    if doa_info.is_near_speaker_direction:
        return False
    return doa_info.confidence > 0.5

def motion_gate_pass(mode):
    if mode == "STRICT":
        return stronger_conditions_met()
    if mode == "MEDIUM":
        return medium_conditions_met()
    return True

while True:
    render_frame = get_current_tts_playback_frame()
    mic_array_frame = read_mic_array_frame()

    beamformed = beamforming_process(mic_array_frame)
    doa_info = estimate_doa(mic_array_frame)

    aec_out = aec3.process(beamformed, render_frame)
    ns_out = noise_suppress(aec_out)

    vad_prob = silero_vad(ns_out)
    residual_rms = calc_rms(ns_out)

    motion_mode = get_robot_motion_gate()

    if state == "IDLE":
        if vad_prob > VAD_IDLE_TH and enough_duration():
            start_asr()
            state = "LISTENING"

    elif state == "TTS_PLAYING":
        hit = (
            vad_prob > VAD_TTS_TH and
            residual_rms > RESIDUAL_TH and
            spatial_gate_pass(doa_info) and
            motion_gate_pass(motion_mode)
        )

        update_candidate_window(candidate_window, hit)
        update_candidate_duration(hit)

        if sliding_window_hit_ratio(candidate_window) > HIT_RATIO_TH and duration_ok():
            pause_tts()
            reset_confirm_state()
            state = "INTERRUPT_CONFIRM"

    elif state == "INTERRUPT_CONFIRM":
        confirm_audio_buffer.append(ns_out)

        if confirm_audio_ready(confirm_audio_buffer):
            text = fast_asr(confirm_audio_buffer)
            confirm_text = text

            if is_true_barge_in(text, doa_info, motion_mode):
                stop_tts()
                reset_candidate_state()
                start_full_asr_with_prefill(confirm_audio_buffer)
                reset_confirm_state()
                state = "LISTENING"
            else:
                resume_tts()
                reset_candidate_state()
                reset_confirm_state()
                state = "TTS_PLAYING"

    elif state == "LISTENING":
        if user_speech_finished():
            run_nlu()

            if should_start_tts():
                start_tts()
                reset_candidate_state()
                reset_confirm_state()
                state = "TTS_PLAYING"
            else:
                reset_candidate_state()
                reset_confirm_state()
                state = "IDLE"
```

---

# 16. 一句话总结

本方案面向人形机器人，核心思想是：

> 利用 AEC 抑制机器人自身外放回声，利用阵列与空间信息增强用户方向语音，利用 VAD、残差能量、滑窗和机器人运动状态构成稳健的候选打断判定，再通过暂停式语义确认和 rollback 机制实现“既能被用户自然打断，又不容易被自身外放和机体噪声误触发”的可落地语音交互系统。

---

# 17. 最终结论

对于人形机器人，推荐采用如下完整策略：

1. **必须保留 AEC**
2. **优先使用麦克风阵列与空间特征**
3. **VAD 放在增强链路后使用**
4. **候选打断必须采用多特征联合判断**
5. **将机器人运动状态纳入门控逻辑**
6. **必须有暂停式确认与 rollback 恢复**
7. **必须设计严格的状态重置规则**
8. **必要时按场景切换参数策略**

这不是一个“只靠 VAD 就能解决”的问题，而是一套面向人形机器人声学现实和产品体验要求的系统级方案。

---
