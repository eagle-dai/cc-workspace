# Invention Disclosure Form (IDF) / 专利交底书

## 1. Title of Invention / 发明名称

**English**  
**Method and System for Reliable Voice Interruption Detection in a Humanoid Robot under Playback and Robot-Generated Noise**

**中文**  
**一种面向人形机器人的外放与机体噪声场景下可靠语音打断检测方法及系统**

---

## 2. Technical Field / 技术领域

**中文**  
本发明涉及人形机器人、语音交互、语音活动检测、声学信号处理以及机器人多模态状态融合领域，具体涉及一种在人形机器人进行外放播报、同时存在机体运动噪声和环境干扰的条件下，可靠检测用户语音打断的方法及系统。

本发明重点关注“打断是否被正确检测”的前端判定机制，尤其适用于机器人在播报过程中仍允许用户随时打断的交互场景。

**English**  
The invention relates to humanoid robots, voice interaction, voice activity detection, acoustic signal processing, and robot-state-aware multimodal fusion, and more particularly to a method and system for reliably detecting a user voice interruption while a humanoid robot is playing back speech and is subject to robot-generated noise and environmental interference.

The invention focuses on the front-end determination of whether an interruption has actually occurred, especially in interaction scenarios where the robot continues speaking while still allowing the user to interrupt at any time.

---

## 3. Background and Problem to Be Solved / 背景技术与要解决的问题

**中文**  
在人形机器人场景中，机器人通常需要同时执行以下任务：

1. 通过扬声器向用户外放播报语音内容；
2. 通过麦克风阵列持续监听用户输入；
3. 在播报过程中允许用户随时打断；
4. 在远场、多说话人、机体运动和环境噪声条件下保持可靠性。

然而，在真实机器人系统中，打断检测并不是简单的“有没有语音”问题，而是如下复杂问题的叠加：

### （1）机器人自身外放声音会重新进入麦克风

机器人通过扬声器播报时，TTS 语音会经空气传播、机体反射、外壳共振和房间混响重新进入麦克风，导致 VAD 或打断检测模块误认为用户正在说话，从而出现“机器人自己打断自己”的问题。

### （2）机器人自身机械噪声会干扰打断检测

人形机器人通常存在以下机体噪声来源：

- 关节电机噪声；
- 减速器和伺服驱动噪声；
- 风扇噪声；
- 底盘或行走机构噪声；
- 转头、挥手、抬臂等动作引起的结构振动；
- 机体腔体共振和壳体摩擦音。

这些噪声在某些频段或短时突发情况下，容易被误判为用户打断语音。

### （3）单纯依赖普通 VAD 会导致误打断或漏打断

现有方案中，很多系统仅在麦克风输入上运行通用 VAD 模块，一旦检测到语音活动便立即停止播放。该方式存在以下缺陷：

- 对外放残余过于敏感，误打断率高；
- 对机械噪声和瞬态冲击噪声鲁棒性差；
- 在为了降低误判而提高阈值后，又会导致用户真实打断时响应迟缓；
- 无法区分“用户真的要打断”和“只是系统自身残余或无意义声音”。

### （4）机器人是远场交互，不是贴耳设备

相比手机、耳机、近讲麦设备，人形机器人通常面对的是：

- 远场用户；
- 多麦克风阵列；
- 多路径反射；
- 多人共处环境；
- 动态姿态和方向变化。

因此，传统在单设备近场上表现良好的打断检测逻辑，在人形机器人上往往失效。

### （5）状态切换不当会导致历史脏数据污染

在播报状态、候选打断状态、确认状态和恢复状态之间切换时，如果不清理滑窗、确认缓存、持续时长统计和临时语义结果，容易出现：

- rollback 后立刻再次误触发；
- 上一轮确认音频污染下一轮判断；
- 旧的候选命中统计穿透到新的交互轮次；
- 系统表现出“莫名其妙频繁打断”的问题。

---

## 4. Existing Solutions and Their Deficiencies / 现有方案及其不足

**中文**  
现有方案通常有以下几类：

### （1）纯 VAD 触发式方案

即在机器人播报期间，持续对麦克风信号进行 VAD 判断，一旦检测到语音活动则停止机器人播报。

该方案实现简单，但存在明显不足：

- 无法区分用户语音与机器人外放残余；
- 无法识别机体噪声和瞬态非语音干扰；
- 对环境变化极其敏感；
- 在机器人场景下误触发率高。

### （2）播放时直接关闭 VAD 的方案

为了避免机器人自己打断自己，一些方案在 TTS 播放期间直接关闭 VAD 或大幅抑制麦克风输入。

该方案虽然减少了误打断，但带来新的问题：

- 用户无法自然打断机器人；
- 交互体验僵硬；
- 机器人无法实现类似人类对话中的“随时插话”。

### （3）仅依赖 AEC 的方案

有些系统引入回声消除后，仍然将 AEC 输出直接作为最终打断依据。

该方案仍存在问题：

- AEC 无法保证完全消除所有残余；
- 在非线性失真、机体共振、房间混响和路径变化条件下，仍会保留较明显残差；
- 双讲场景下残差可能瞬时增大；
- 单靠 AEC 输出仍不足以判断是否真的发生用户打断。

### （4）无机器人状态感知的语音检测方案

现有多数语音检测方案没有把机器人自身状态纳入判定逻辑，例如：

- 机器人是否正在走路；
- 是否正在快速转头；
- 是否存在高负载关节动作；
- 风扇是否高速运转；
- 当前扬声器播放音量是否较大。

这会导致系统在机器人运动过程中大量误判。

因此，需要一种专门面向人形机器人场景的可靠打断检测方案，用于在外放、机体噪声、远场、阵列麦、多状态切换的复杂条件下，仍然稳定地区分“真实用户打断”和“系统自身造成的伪打断”。

---

## 5. Core Idea of the Invention / 发明核心思想

**中文**  
本发明提出一种面向人形机器人的可靠语音打断检测方法及系统，其核心思想是：

1. 在机器人播报期间，不直接以“检测到语音活动”作为打断条件；
2. 先对麦克风阵列信号进行空间增强和方向估计，再对外放回声和环境噪声进行抑制；
3. 将外放参考信号、增强后的语音活动信息、残差能量、持续时长、空间方向以及机器人自身运动状态共同作为候选打断的判据；
4. 当候选条件满足时，并不立即永久终止播报，而是先暂停播报进入短暂确认阶段；
5. 在确认阶段，利用短时 ASR、打断词识别或语义判断确认是否为真实用户打断；
6. 若确认是真打断，则正式中止播报并进入用户输入处理；
7. 若确认不是有效打断，则执行 rollback，恢复播报；
8. 在状态迁移过程中，严格重置用于短时判定的缓存和统计量，防止历史脏数据污染新的判断。

该方案重点解决的是：

- 机器人外放条件下的误打断问题；
- 机器人机体噪声导致的误触发问题；
- 用户真实打断响应不及时的问题；
- 纯声学判断不稳定的问题；
- 状态切换后误触发累积的问题。

**English**  
The invention provides a reliable voice interruption detection method and system for a humanoid robot. The core idea is as follows:

1. during robot speech playback, the system does not treat any detected speech activity as an interruption by default;
2. microphone-array signals are first spatially enhanced and directionally analyzed, and playback echo and noise are then suppressed;
3. playback-reference information, enhanced speech activity, residual energy, duration, spatial direction, and robot-motion states are jointly used to determine a candidate interruption;
4. when candidate conditions are met, the system does not immediately and permanently terminate playback, but first pauses playback and enters a short confirmation stage;
5. during the confirmation stage, short-window ASR, interruption-word recognition, or semantic analysis is used to verify whether a true user interruption has occurred;
6. if confirmed, playback is terminated and user input processing starts;
7. otherwise, rollback is performed and playback resumes; and
8. short-term decision caches and counters are reset on state transitions to prevent stale data from contaminating subsequent decisions.

---

## 6. Distinction from Other Interaction-Continuity Schemes / 与其他“打断后连续执行”方案的区分

**中文**  
本发明的重点不是“打断发生后如何隔离旧回合语音、如何保持云端任务连续执行”，而是：

> **在复杂机器人声学条件下，如何更可靠地检测“用户是否真的正在打断机器人”。**

换言之，本发明关注的是**打断检测前端**，而非打断发生后的任务上下文管理、旧回合锁定、恢复控制消息或云边任务连续更新。

本发明更偏向：

- 机器人场景的 VAD 增强；
- 抗外放误触发；
- 抗机体噪声误触发；
- 空间与运动状态融合；
- 候选打断判定与确认；
- rollback 恢复；
- 状态重置机制。

因此，本发明适合独立作为一条“机器人场景打断检测”技术主线进行保护。

**English**  
The invention is not primarily concerned with how stale prior-turn speech is isolated after an interruption, nor with how cloud-side task continuity is preserved after interruption. Instead, the invention focuses on:

> **how to more reliably determine, under complex robotic acoustic conditions, whether a user is truly interrupting the robot.**

In other words, the invention concerns the front-end interruption-detection logic rather than post-interruption turn management, prior-turn locking, resume-control signaling, or cloud-task continuity.

---

## 7. Technical Solution / 技术方案

### 7.1 System Architecture / 系统架构

**中文**  
本发明所述系统可包括以下模块：

1. **播放模块**  
   用于将机器人待播报的语音数据输出到扬声器，并生成对应的播放参考音频流。

2. **麦克风阵列采集模块**  
   用于采集来自机器人周围环境的多通道音频信号。

3. **空间增强模块**  
   用于对多通道音频进行波束形成、声源方向估计和空间特征提取。

4. **回声抑制模块**  
   用于根据播放参考流，对采集音频中的机器人自身外放回声进行消除或抑制。

5. **噪声抑制模块**  
   用于抑制环境噪声和部分机体底噪，必要时还可包括去混响处理。

6. **语音活动检测模块**  
   用于输出经增强后的语音活动概率、语音片段候选或其他语音存在性指标。

7. **机器人状态获取模块**  
   用于获取机器人当前姿态、动作状态、关节负载、风扇状态、行走状态、头部运动状态和扬声器音量状态等。

8. **候选打断判定模块**  
   用于综合语音活动概率、残差能量、持续时长、滑窗命中率、空间特征和机器人状态，判定是否形成候选打断事件。

9. **确认判定模块**  
   用于在候选打断出现后，暂停播报、收集确认音频，并通过打断词识别、短时 ASR 或语义判断来确认是否是真打断。

10. **恢复控制模块**  
    用于在误打断场景下恢复原播报。

11. **状态管理与重置模块**  
    用于在不同状态切换时，清理短时缓存和统计量，避免历史脏数据污染新的判定。

---

### 7.2 Signal Processing Pipeline / 信号处理链路

**中文**  
在一实施方式中，机器人在播报期间的处理链路可为：

```text
TTS 播放流
  ├─→ 扬声器播放
  └─→ 播放参考流

麦克风阵列输入
  ├─→ 波束形成
  ├─→ 声源方向估计
  ├─→ 回声消除 / 回声抑制
  ├─→ 噪声抑制 / 可选去混响
  └─→ 语音活动检测

语音活动检测输出 + 残差能量 + 持续时长 + 滑窗统计
          + 声源方向信息 + 机器人状态信息
  └─→ 候选打断判定

候选打断成立
  └─→ 暂停播报
  └─→ 确认阶段（短时 ASR / 打断词 / 语义判断）
      ├─→ 真打断：停止播报并进入用户输入
      └─→ 误打断：rollback 恢复播报
```

该链路的关键点在于：

- VAD 不是单独使用；
- 空间信息不是可有可无的附加项，而是重要辅助证据；
- 机器人状态被纳入门控逻辑；
- 候选打断与真打断分层判断；
- 确认失败时允许恢复播报。

---

### 7.3 Playback Reference-Aware Acoustic Processing / 基于播放参考流的回声感知处理

**中文**  
在本发明中，机器人在通过扬声器播报语音时，系统生成与实际播放内容对应的播放参考流。回声抑制模块利用该播放参考流，对麦克风采集音频中由机器人自身播报引起的回声成分进行抑制或抵消。

优选地，该播放参考流尽量接近实际送往扬声器的最终音频流，而不是仅使用文本、上游合成参数或与播放链路偏离较大的中间信号。

这样做的目的是降低由自身播报导致的伪语音活动响应。

在一些实施方式中，所述回声抑制模块可结合延迟估计与对齐机制，以减小因音频缓冲、设备差异或链路延迟变化带来的对齐偏差。

---

### 7.4 Spatially Assisted Candidate Interruption Determination / 基于空间特征辅助的候选打断判定

**中文**  
在本发明中，候选打断并非仅依据单一语音活动结果，而是综合如下信息进行判断：

1. 语音活动检测模块输出的语音概率或语音存在指标；
2. 回声抑制后残余信号的能量或强度信息；
3. 满足条件的持续时长；
4. 在预定时间窗口内满足条件的命中比例；
5. 声源方向是否接近用户所在方向；
6. 声源方向是否接近扬声器方向；
7. 当前机器人是否处于高机械噪声状态；
8. 当前机器人是否处于行走、快速转头或高速动作状态。

在一些实施方式中，若检测到语音方向更接近用户正前方或机器人当前关注方向，则降低打断触发门限；若方向更接近扬声器方向或明显不稳定，则提高打断门限或拒绝形成候选打断。

---

### 7.5 Robot-State-Aware Gating / 基于机器人状态的门控机制

**中文**  
本发明将机器人自身状态作为打断判定的重要输入，而不是仅将机器人视为普通音频设备。

可接入的机器人状态包括但不限于：

- 是否正在行走；
- 是否正在快速转头；
- 是否存在高负载关节动作；
- 是否存在明显的结构振动；
- 风扇是否处于高转速状态；
- 当前扬声器播放音量是否较高。

在一些实施方式中，系统根据不同机器人状态动态调整候选打断的判定条件，例如：

- 在静止状态下降低门限，提高交互自然性；
- 在行走状态下提高门限，抑制步态噪声干扰；
- 在快速转头或高速动作瞬间临时冻结或弱化候选打断触发；
- 在高音量播报时提高残差相关判定门限。

---

### 7.6 Two-Stage Interruption Decision / 双阶段打断判定

**中文**  
本发明优选采用双阶段打断判定机制：

#### 第一阶段：候选打断

当声学与状态特征满足预定条件时，形成候选打断事件，但此时不立即永久终止播报。

#### 第二阶段：确认打断

在候选打断形成后，系统暂停当前播报，并在短时间窗口内收集确认音频，再通过以下至少一种方式确认是否为真实打断：

- 打断词识别；
- 机器人名字识别；
- 短时 ASR；
- 基于 ASR 结果的语义判断；
- 基于正在播报文本的语义相似性排除。

若确认是真打断，则停止当前播报并切换至用户输入处理；若确认不是有效打断，则恢复原播报。

通过这种两阶段机制，可以避免“检测到一点声音就永久停播”的问题。

---

### 7.7 Semantic Rollback / 语义 rollback 机制

**中文**  
在一实施方式中，确认阶段若检测到如下情形之一，则认定不构成真实打断：

- 咳嗽、呼气、短促无意义发声；
- “啊”“哦”“嗯”等无明确指令意图的语气词；
- 与当前正在播报的 TTS 文本高度重合的内容；
- 缺乏明确用户意图的短时语音片段。

在上述情况下，系统执行 rollback，即：

1. 恢复此前暂停的播报；
2. 清理本次候选打断和确认阶段的短时缓存；
3. 继续维持播报状态下的打断监听。

---

### 7.8 State Reset Mechanism / 状态重置机制

**中文**  
本发明特别强调在不同状态之间切换时，对短时缓存和统计量进行规则化重置。

需要重置的内容可以包括但不限于：

- 候选打断滑窗缓存；
- 连续命中计数；
- 候选打断持续时长计数；
- 确认音频缓存；
- 临时识别文本；
- rollback 标记；
- 其他仅在当前短时判定中有效的临时状态。

而对于回声消除器、波束形成器、降噪器或流式 VAD 的长期内部自适应状态，则可以在状态切换时保留，仅在设备切换、采样率变化、链路重启或音频结构变化时再执行重建或重置。

该状态重置机制可显著减少以下问题：

- rollback 后立即再次误触发；
- 旧确认音频污染新一轮判断；
- 历史命中窗口穿透到下一轮交互。

---

## 8. State Machine / 状态机设计

### 8.1 State Definitions / 状态定义

**中文**

#### （1）空闲监听状态 `Idle`

机器人未播报，仅监听用户语音。

#### （2）用户输入状态 `Listening`

机器人检测到用户正在说话，并将音频送往正式识别处理。

#### （3）播报监听状态 `PlaybackMonitoring`

机器人正在播报，同时持续监听用户是否尝试打断。

#### （4）候选打断状态 `InterruptCandidate`

系统已根据声学、空间和机器人状态信息判断出可能存在打断迹象。

#### （5）确认状态 `InterruptConfirm`

系统暂停播报，收集确认音频，并执行短时确认。

#### （6）真打断状态 `TrueInterrupt`

确认用户真实打断，停止播报并进入用户输入。

#### （7）恢复状态 `RollbackResume`

确认不是真打断，恢复播报并返回播报监听状态。

---

### 8.2 State Transitions / 状态转移

**中文**

```text
Idle
 └─(检测到用户语音)→ Listening

Listening
 └─(用户说完且机器人开始播报)→ PlaybackMonitoring

PlaybackMonitoring
 └─(形成候选打断)→ InterruptConfirm

InterruptConfirm
 ├─(确认是真打断)→ Listening
 └─(确认是误触发)→ PlaybackMonitoring
```

在具体实现中，`InterruptCandidate` 可以作为内部逻辑状态，也可以作为 `PlaybackMonitoring` 中的子状态实现。

---

## 9. Detailed Decision Rules / 详细判定规则

### 9.1 Candidate Interruption Rule / 候选打断判定规则

**中文**  
在一实施方式中，候选打断可基于如下复合条件形成：

```text
候选打断成立 =
    语音活动概率超过第一门限
AND 残余能量超过第二门限
AND 满足条件的持续时长超过第三门限
AND 在预定滑窗中的命中率超过第四门限
AND 空间门控条件通过
AND 机器人状态门控条件通过
```

其中：

- **空间门控条件**可包括：
  - 声源方向接近用户方向；
  - 声源方向不接近扬声器方向；
  - 或方向估计置信度高于预定门限。

- **机器人状态门控条件**可包括：
  - 当前不处于高机械噪声风险模式；
  - 或者在高风险模式下满足更严格的候选门限。

该候选打断规则相比传统单一 VAD 判定具有更强鲁棒性。

---

### 9.2 Confirmation Rule / 确认规则

**中文**  
当候选打断形成后，系统暂停播报，并在短时窗口内收集确认音频。随后执行至少一种确认方式：

1. 打断词匹配；
2. 机器人名称匹配；
3. 短时 ASR；
4. 基于文本内容的语义意图判断；
5. 与当前播报文本的相似性比较。

若确认结果表明用户正在发起新指令、修正或明确打断，则认定为真打断；否则视为误触发并恢复播报。

---

### 9.3 Dynamic Threshold Strategy / 动态门限策略

**中文**  
在一实施方式中，不同机器人状态下采用不同的门限策略：

#### 静止模式

- 适用于机器人静止、环境相对安静、用户方向明确的情形；
- 可采用相对灵敏的候选打断门限。

#### 行走模式

- 适用于机器人步行、底盘运动或显著机械噪声状态；
- 提高候选打断门限；
- 增大确认所需时长；
- 必要时仅允许特定打断词触发。

#### 快速动作模式

- 适用于转头、挥手、抬臂等快速机械动作；
- 可临时冻结弱候选打断；
- 或仅允许通过语义确认后再中止播报。

#### 高音量播报模式

- 适用于机器人在嘈杂环境中提高播报音量的情形；
- 提高残余能量相关门限；
- 对短促语音更保守；
- 优先依赖双阶段确认。

---

## 10. Example Workflow / 技术实施例

**中文**  
以下以人形机器人在展厅讲解场景中的交互为例说明本发明。

1. 机器人正在向用户讲解展品信息，并通过扬声器持续播报。  
   此时机器人处于 `PlaybackMonitoring` 状态。

2. 机器人麦克风阵列持续采集环境音频，波束形成模块增强正前方用户方向信号，回声抑制模块基于当前播放参考流降低机器人自身播报残余。

3. 在播报过程中，用户试图插话说：“等一下，这个展品可以拍照吗？”  
   处理后的音频在短时间内表现出：
   - 语音活动概率升高；
   - 回声抑制后仍有明显残余人声成分；
   - 信号方向接近用户正前方；
   - 当前机器人处于静止状态；
   - 满足预定持续时长和滑窗命中率要求。

4. 候选打断判定模块据此形成候选打断事件，系统暂停当前播报，进入 `InterruptConfirm` 状态。

5. 在确认阶段，机器人收集后续约数百毫秒确认音频，并通过短时 ASR 检测到“等一下”和后续问题片段。  
   系统据此认定为用户真实打断，停止原播报，进入 `Listening` 状态，将该确认音频前缀并入正式识别。

6. 另一场景下，若机器人在播报时采集到一段由扬声器残余和短促机械声叠加形成的瞬时干扰，虽然短时内也可能引发语音活动概率升高，但：
   - 声源方向接近扬声器方向；
   - 机械动作状态处于高风险模式；
   - 确认阶段未识别出有效打断词或明确语义。

   此时系统将该事件视为误触发，并执行 rollback，恢复原播报。

通过上述流程，机器人既能保持自然可打断交互，又能避免被自身播报和机体噪声频繁误触发。

---

## 11. Key Novelty Points / 创新点总结

**中文**  
本发明的创新点可概括为以下几点：

1. **面向人形机器人，而非普通终端设备，专门解决外放与机体噪声条件下的用户打断检测问题；**
2. **将播放参考流参与的回声抑制、空间方向信息、机器人运动状态和语音活动信息联合用于候选打断判定；**
3. **候选打断与真打断分层处理，而不是检测到语音即直接停播；**
4. **引入暂停式确认和 rollback 恢复机制，降低误打断对交互体验的破坏；**
5. **在状态迁移时重置短时缓存和统计量，防止历史脏数据引发连环误触发；**
6. **通过机器人状态门控，使打断检测逻辑能够适应静止、行走、快速动作和高音量播报等不同工作模式。**

**English**  
The novelty may be summarized as follows:

1. the invention is specifically directed to humanoid robots rather than general terminals, and addresses interruption detection under playback and robot-generated noise;
2. playback-reference-aware echo suppression, spatial-direction information, robot-motion states, and speech-activity information are jointly used for candidate interruption determination;
3. candidate interruption and confirmed interruption are handled in separate stages, rather than stopping playback immediately upon speech detection;
4. pause-based confirmation and rollback recovery are introduced to reduce interaction damage caused by false triggers;
5. short-term caches and counters are reset on state transitions to prevent chain false triggers caused by stale data; and
6. robot-state-aware gating allows the interruption-detection logic to adapt to stationary, walking, fast-motion, and high-volume playback modes.

---

## 12. Benefits / 有益效果

**中文**  
与现有方案相比，本发明至少具有如下有益效果：

1. 能够显著降低机器人在外放场景下“自己打断自己”的问题；
2. 能够降低由机械噪声、风扇噪声、动作振动等引起的误触发；
3. 能在不关闭播报期间打断能力的前提下，提高用户自然打断的可用性；
4. 能通过双阶段确认降低单次误判对整体体验的破坏；
5. 能通过状态重置机制提高长期运行稳定性；
6. 更适合人形机器人远场、多麦阵列、复杂动作和动态环境条件下的语音交互。

---

## 13. Optional Embodiments / 可选实施方式

**中文**  
在不同实施方式中，本发明还可进一步包括以下可选改进：

### （1）打断词优先模式

在机械噪声较大的状态下，仅允许“停一下”“等等”“不是”等预定义打断词触发快速中止。

### （2）视觉或头部朝向辅助

利用摄像头、人体跟踪结果或机器人头部朝向信息，提高对用户方向的估计准确性。

### （3）多说话人场景优先级

结合说话人定位、身份或距离信息，优先接受机器人当前面向用户的打断请求。

### （4）去混响增强

在大厅、展馆或高混响环境中，增加去混响模块，提高确认阶段准确性。

### （5）设备切换后的链路重建

在音频设备、采样率或播放链路发生变化时，执行回声、阵列和状态模块的重建或重新初始化。

---

## 14. Claim Drafting Hints / 权利要求起草建议

**中文**  
后续若交由专利律师起草，建议重点保护以下几个独立主线：

### 方法权利要求主线

- 在机器人播报期间采集麦克风阵列信号；
- 基于播放参考流对采集信号中的自身播报成分进行抑制；
- 提取语音活动信息、残差信息、空间方向信息和机器人状态信息；
- 基于上述信息联合形成候选打断；
- 暂停播报并进行确认；
- 根据确认结果选择停止播报或恢复播报；
- 在状态切换时重置短时缓存和统计量。

### 系统权利要求主线

- 播放模块；
- 麦克风阵列采集模块；
- 空间增强模块；
- 回声抑制模块；
- 噪声抑制模块；
- 候选打断判定模块；
- 确认判定模块；
- 状态重置模块；
- 恢复控制模块。

### 从属点建议

- 空间方向门控规则；
- 机器人运动状态门控规则；
- 播放音量相关门限调整；
- 候选打断与真打断的双阶段结构；
- rollback 恢复机制；
- 打断词优先模式；
- 滑窗、持续时长和命中率条件；
- 长期状态与短时状态的不同重置策略。

---

## 15. One-Sentence Summary / 一句话总结

**中文**  
本发明提出一种面向人形机器人的可靠语音打断检测方法及系统，通过将播放参考流参与的回声抑制、空间方向信息、语音活动检测、机器人运动状态和双阶段确认机制结合起来，使机器人能够在外放播报、机体噪声和动态动作条件下，既允许用户自然打断，又不易被自身外放和机械噪声误触发。

**English**  
The invention provides a reliable interruption-detection method and system for a humanoid robot by combining playback-reference-aware echo suppression, spatial-direction information, speech activity detection, robot-motion states, and a two-stage confirmation mechanism, thereby allowing natural user interruption during robot playback while reducing false triggers caused by the robot's own playback and mechanical noise.

---
