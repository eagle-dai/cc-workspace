# Invention Disclosure Form (IDF) / 专利交底书

## 1. Title of Invention / 发明名称

**English**  
**Method and System for Voice Interruption Isolation and Continuous Task Execution in a Humanoid Robot**

**中文**  
**一种面向人形机器人的语音打断隔离与任务连续执行方法及系统**

---

## 2. Technical Field / 技术领域

**中文**  
本发明涉及人形机器人、人机语音交互以及云边协同任务执行领域，具体涉及一种在人形机器人接收用户语音打断时，对旧回合语音进行本地隔离、并在不中断云端任务上下文的情况下实现任务连续更新的方法及系统。

**English**  
The invention relates to humanoid robots, human-robot voice interaction, and cloud-edge collaborative task execution, and more particularly to a method and system for locally isolating stale speech associated with an interrupted turn and continuously updating a cloud-side task context without terminating the task when a humanoid robot receives a user voice interruption.

---

## 3. Problem to Be Solved / 要解决的问题

**中文**  
在人形机器人场景中，机器人通常一边通过语音与用户持续交互，一边依赖云端或远端计算资源完成高时延任务，例如环境理解、多步任务规划、目标检索、动作编排、跨系统任务查询或企业流程联动。

在这类系统中，用户经常会在机器人播报过程中或任务执行过程中临时打断，并补充新的语音约束，例如：

- 修改目的地；
- 更换目标对象；
- 增加避障要求；
- 调整动作顺序；
- 临时改变交付对象；
- 增加安全边界限制。

现有方案在处理这类语音打断时，通常存在以下两个问题：

### （1）上一轮语音的残余数据可能在打断后继续播放

很多系统在检测到用户打断后，只是停止当前正在播放的语音。  
但由于网络传输延迟、云端流水线尚未完全停止，或者边缘侧已经缓存了部分后续数据，上一轮交互生成的后续语音数据仍可能继续到达人形机器人，并重新进入本地播放队列。  
这会导致过期播报、语义混淆，甚至影响用户对机器人当前行为的判断。

### （2）交互打断常被等同于任务终止

很多系统把“用户打断当前语音输出”与“终止当前任务执行流程”绑定处理。  
但在人形机器人场景中，用户打断通常不是为了取消整个任务，而是为了在任务持续执行的基础上做局部修正。  
如果每次打断都直接中止云端已有任务上下文并从头重算，会造成算力浪费，增加响应延迟，也不利于复杂任务的连续执行。

因此，需要一种新的技术方案，使人形机器人在用户语音打断后，既能在本地可靠隔离旧回合残余语音，又能保留云端任务上下文，并基于新增语音约束继续完成更新后的任务。

**English**  
In humanoid robot scenarios, a robot often maintains continuous voice interaction with a user while relying on cloud-side or remote computing resources to perform high-latency tasks such as environment understanding, multi-step task planning, target retrieval, action orchestration, cross-system task querying, or enterprise workflow coordination.

In such systems, a user frequently interrupts the robot during speech output or task execution and provides updated voice constraints, for example:

- changing a destination;
- replacing a target object;
- adding an obstacle-avoidance requirement;
- adjusting action order;
- changing a delivery recipient; or
- adding a safety-boundary restriction.

Existing approaches typically suffer from the following two issues:

### (1) residual speech from a previous turn may still be played after interruption

Many systems simply stop the speech that is currently being played once an interruption is detected.  
However, because of network delay, incomplete shutdown of the cloud pipeline, or data already buffered at the edge side, subsequent speech data generated for the previous interaction turn may still arrive at the humanoid robot and re-enter the local playback queue.  
This can cause outdated speech output, semantic confusion, and even incorrect user understanding of the robot’s current behavior.

### (2) interruption of interaction is often treated as task termination

Many systems bind “interrupting current speech output” together with “terminating the current task execution flow.”  
In humanoid robot scenarios, however, a user interruption often does not mean cancellation of the whole task, but rather a local correction while the task should continue.  
If every interruption causes an existing cloud-side task context to be terminated and recomputed from scratch, computing resources are wasted, response latency increases, and continuity of complex task execution is degraded.

Accordingly, a new technical solution is needed so that, after a user voice interruption, a humanoid robot can both reliably isolate residual speech associated with a prior turn at the robot side and preserve the cloud-side task context so that the updated task can continue.

---

## 4. Summary of the Invention / 发明内容概述

**中文**  
本发明提出一种面向人形机器人的语音打断处理方法。  
该方法将“本地语音输出控制”与“云端任务执行连续性”分开处理。

其基本思路如下：

1. 机器人边缘侧检测到用户语音打断后，立即停止当前语音输出，并清空本地缓存与待播放队列；
2. 边缘侧进入与被打断回合相关联的锁定状态；
3. 在锁定状态下，边缘侧依据数据包中的回合标识，对后续到达的语音或控制数据进行校验；
4. 属于被打断旧回合的语音数据，在进入本地播放队列之前直接丢弃；
5. 同时，边缘侧不请求云端终止当前任务实例，而是将新的语音输入转换为对原任务的增量约束更新；
6. 云端在保留原任务上下文的基础上，根据增量约束进行局部更新或重规划；
7. 云端生成新的交互回合并返回恢复控制消息；
8. 机器人边缘侧在校验恢复控制消息满足条件后，解除锁定，并允许新回合语音接管本地播放。

通过该方法，可以同时解决两个问题：  
一方面，避免打断后旧回合语音残留误播；另一方面，避免云端长时任务因一次交互打断而被整体销毁和重建。

**English**  
The invention provides a voice interruption handling method for a humanoid robot.  
The method decouples “local speech output control” from “cloud-side task execution continuity.”

The basic idea is as follows:

1. once a user voice interruption is detected at the robot edge side, the robot immediately stops current speech output and clears local buffers and pending playback queues;
2. the edge side enters a locked state associated with the interrupted turn;
3. while in the locked state, the edge side validates subsequently arriving speech or control data based on turn identifiers carried in packets;
4. speech data belonging to the interrupted prior turn are directly discarded before entering the local playback queue;
5. meanwhile, the edge side does not request the cloud to terminate the current task instance, but instead converts the new voice input into incremental constraint updates to the original task;
6. the cloud preserves the original task context and performs local updating or replanning according to the incremental constraints;
7. the cloud generates a new interaction turn and returns a resume control message; and
8. after validating that the resume control message satisfies an unlock condition, the robot edge side exits the locked state and allows speech associated with the new turn to take over local playback.

This approach simultaneously solves two problems:  
on the one hand, it prevents stale speech of a prior turn from being mistakenly played after interruption; on the other hand, it avoids destroying and rebuilding a long-running cloud task merely because of a single interaction interruption.

---

## 5. Core Technical Solution / 核心技术方案

### 5.1 Turn-Based Packet Identification / 基于回合的数据标识

**中文**  
系统为每一轮语音交互分配唯一的回合标识 `turn_id`。  
当新的交互回合是在上一回合基础上形成的修正回合时，还携带 `parent_turn_id`，用于表示其与被打断旧回合之间的关联关系。

云边之间传输的控制消息和语音消息可以至少包括以下字段：

- `turn_id`：当前消息所属的交互回合标识；
- `parent_turn_id`：当前回合所关联的上一回合标识；
- `message_type`：消息类型，用于区分语音数据、状态消息、恢复控制消息等。

**English**  
The system assigns a unique `turn_id` to each voice interaction turn.  
When a new interaction turn is a corrective turn generated on top of a previous turn, the new turn further carries a `parent_turn_id` indicating its relationship with the interrupted prior turn.

Control messages and speech messages transmitted between cloud and edge may include at least the following fields:

- `turn_id`: an interaction turn identifier associated with the current message;
- `parent_turn_id`: an identifier of a previous turn associated with the current turn;
- `message_type`: a message type used to distinguish speech data, status messages, resume control messages, and the like.

---

### 5.2 Edge-Side State Machine / 边缘侧状态机

**中文**  
机器人边缘侧维护与语音输出相关的状态机，至少包括如下状态：

- `Idle`：空闲状态；
- `Active(Tn)`：当前正在输出回合 `Tn` 的语音；
- `Cancelled(Tn)`：检测到对回合 `Tn` 的打断后，执行停止与清空动作的过渡状态；
- `AwaitingResume(Tn)`：已完成停止与清空，等待新回合恢复接管的状态。

当机器人处于 `Active(Tn)` 状态并检测到用户打断输入时，边缘侧执行以下动作：

1. 立即停止当前语音播放；
2. 清空本地播放缓存、待播放队列或相关渲染缓冲；
3. 记录被打断回合标识 `Tn`；
4. 从 `Cancelled(Tn)` 自动进入 `AwaitingResume(Tn)`。

**English**  
The robot edge side maintains a state machine associated with speech output, including at least:

- `Idle`: an idle state;
- `Active(Tn)`: a state in which speech associated with turn `Tn` is currently being output;
- `Cancelled(Tn)`: a transitional state entered after detecting an interruption to turn `Tn`, during which stop and flush operations are performed;
- `AwaitingResume(Tn)`: a state entered after stop and flush operations are complete, while waiting for a new turn to take over.

When the robot is in `Active(Tn)` and detects a user interruption input, the edge side performs the following:

1. immediately stopping current speech playback;
2. clearing a local playback buffer, pending playback queue, or associated rendering buffer;
3. recording the interrupted turn identifier `Tn`; and
4. automatically transitioning from `Cancelled(Tn)` to `AwaitingResume(Tn)`.

---

### 5.3 Stale Speech Isolation Before Playback / 播放前的旧语音隔离

**中文**  
在 `Cancelled(Tn)` 或 `AwaitingResume(Tn)` 状态下，机器人边缘侧对后续到达的数据执行基于回合标识的校验。

对于未满足解锁条件的数据，执行如下处理：

- 若数据属于被打断旧回合 `Tn` 的普通语音消息，则直接丢弃，不进入本地队列；
- 若数据属于其他新回合，但尚未获得与当前锁定状态匹配的恢复控制授权，也不进入本地队列；
- 仅允许满足预设条件的恢复控制消息进入解锁流程。

该隔离动作发生在本地语音播放之前，即发生在数据接收、入队或渲染前处理阶段，而不是在语音已经进入播放链路后再做被动停止。

**English**  
While in `Cancelled(Tn)` or `AwaitingResume(Tn)`, the robot edge side validates subsequently arriving data based on turn identifiers.

For data that do not satisfy an unlock condition, the following handling applies:

- if the data belong to ordinary speech messages of interrupted prior turn `Tn`, the data are directly discarded and are not admitted into the local queue;
- if the data belong to another new turn but no resume control authorization matching the current locked state has yet been received, the data likewise are not admitted into the local queue; and
- only a resume control message satisfying a predefined condition is allowed to enter an unlock procedure.

This isolation is performed before local speech playback, namely at a data receiving stage, queue admission stage, or rendering pre-processing stage, rather than passively stopping speech after the speech has already entered a playback path.

---

### 5.4 Cloud Task Continuity and Incremental Update / 云端任务连续执行与增量更新

**中文**  
用户打断后，机器人边缘侧不将该打断视为对原任务实例的终止指令。  
相反，边缘侧将打断后的新语音输入解析为对原任务的增量更新信息，并发送给云端。

所述增量更新信息可以包括一种或多种形式：

- 结构化参数更新；
- 半结构化约束表达；
- 通过语义解析得到的任务修正表示。

在人形机器人语音任务场景中，增量更新信息可包括但不限于：

- 目标地点更新；
- 目标对象替换；
- 禁行区域或避障区域更新；
- 动作顺序调整；
- 交付对象变更；
- 安全边界或接近限制更新；
- 任务优先级调整。

云端在接收到上述增量更新信息后，保留原任务上下文、执行流程、计算图或中间结果，仅对受影响部分执行更新、重规划或重新排序，而不销毁整个任务实例。

**English**  
After a user interruption, the robot edge side does not treat the interruption as a termination command for the original task instance.  
Instead, the edge side parses the new voice input into incremental update information for the original task and sends the information to the cloud.

The incremental update information may take one or more of the following forms:

- structured parameter updates;
- semi-structured constraint expressions; or
- task correction representations produced through semantic parsing.

In a humanoid robot voice-task scenario, the incremental update information may include, but is not limited to:

- destination updates;
- target object replacement;
- no-go zone or obstacle-avoidance region updates;
- action order adjustment;
- delivery recipient change;
- safety boundary or proximity restriction updates; and
- task priority adjustment.

Upon receiving such incremental update information, the cloud preserves the original task context, execution flow, computation graph, or intermediate results, and updates, replans, or reorders only affected parts instead of destroying the entire task instance.

---

### 5.5 Resume Authorization and New-Turn Takeover / 恢复授权与新回合接管

**中文**  
云端基于增量更新完成局部处理后，生成新的交互回合 `T2`，并向机器人边缘侧发送恢复控制消息。  
该恢复控制消息可携带：

- `turn_id = T2`；
- `parent_turn_id = T1`，其中 `T1` 为当前处于锁定状态的被打断旧回合。

机器人边缘侧在接收到恢复控制消息后，判断该消息是否与当前锁定的旧回合匹配。  
若匹配，则解除 `AwaitingResume(T1)` 状态，并允许与 `T2` 关联的语音消息进入本地队列和播放链路，使新回合接管输出。

**English**  
After completing local processing based on the incremental update, the cloud generates a new interaction turn `T2` and sends a resume control message to the robot edge side.  
The resume control message may carry:

- `turn_id = T2`; and
- `parent_turn_id = T1`, where `T1` is the interrupted prior turn currently associated with the locked state.

After receiving the resume control message, the robot edge side determines whether the message matches the prior turn currently locked by the edge side.  
If matched, the edge side exits `AwaitingResume(T1)` and admits speech messages associated with `T2` into the local queue and playback path, thereby allowing the new turn to take over output.

---

### 5.6 Fail-Safe Handling / 异常与容错处理

**中文**  
若恢复控制消息在预设时间窗口内未到达，机器人边缘侧可以继续保持锁定状态，并拒绝旧回合语音进入播放队列。  
同时，系统可允许用户发起新的语音输入，或者触发重新建联、重新初始化新回合等恢复动作，以避免系统停留在不确定状态。

**English**  
If the resume control message does not arrive within a predefined time window, the robot edge side may remain in the locked state and continue rejecting prior-turn speech from entering the playback queue.  
At the same time, the system may allow the user to initiate further voice input, or trigger reconnection or initialization of a new turn so as to avoid leaving the system in an uncertain state.

---

## 6. Optional Embodiments / 可选实施方式

**中文**  
作为可选实施方式，机器人边缘侧还可维护回合内的语音优先级队列。  
例如，可将确认类提示、状态类提示和结果类播报设置为不同优先级。

在正常输出状态下，边缘侧可根据优先级对队列进行调度，以改善用户感知延迟。  
在打断及恢复过程中，还可进一步执行以下操作：

- 对已入队但属于旧回合的低优先级语音执行失效标记或直接移除；
- 对重复状态提示进行去重或合并；
- 避免恢复后继续播报已经过期的中间状态语音。

**English**  
As an optional embodiment, the robot edge side may further maintain an intra-turn speech priority queue.  
For example, acknowledgment prompts, status prompts, and result announcements may be assigned different priorities.

During normal output, the edge side may schedule the queue according to priority so as to improve perceived latency.  
During interruption and recovery, the edge side may further:

- invalidate or directly remove low-priority speech items already queued but belonging to the prior turn;
- deduplicate or merge repeated status prompts; and
- avoid outputting obsolete intermediate-status speech after recovery.

---

## 7. Example Workflow / 技术实施例

**中文**  
以下以人形机器人执行语音指令任务为例说明本发明。

1. 用户对人形机器人说：“去前台接访客，然后把文件送到三号会议室。”  
   机器人边缘侧生成第一回合 `T1`，并将任务请求发送至云端。

2. 云端启动与 `T1` 相关的任务上下文，执行访客接待、导航路径和后续递送流程的规划，并开始向机器人返回确认语音和状态语音。

3. 机器人正在播报过程中，用户再次打断：“先不要去会议室，先把文件交给门口的李工，避开电梯口那一片区域。”

4. 机器人边缘侧检测到该语音打断后，立即停止当前播报，清空本地语音缓存和待播放队列，并进入 `AwaitingResume(T1)` 状态。

5. 由于网络延迟，云端之前为 `T1` 生成的后续语音仍继续到达机器人边缘侧。  
   机器人根据当前锁定状态和数据中的 `turn_id` 识别出这些语音属于旧回合 `T1`，因此在入队前直接丢弃，不再播放。

6. 机器人将新的语音输入解析为增量约束，包括“交付对象改为李工”和“新增避开电梯口区域”，并发送给云端。

7. 云端保留原任务上下文，不终止原任务实例，而是在现有规划基础上更新目标对象和路径约束，生成新的回合 `T2`，并发送包含 `parent_turn_id = T1` 的恢复控制消息。

8. 机器人边缘侧校验该恢复控制消息与当前锁定回合匹配后，解除锁定，允许 `T2` 的语音输出进入本地播放，并按照更新后的任务继续执行。

**English**  
An example in which a humanoid robot performs a voice-instructed task is described below.

1. A user says to the humanoid robot: “Go to the front desk to greet a visitor, and then deliver the document to Meeting Room 3.”  
   The robot edge side generates a first turn `T1` and sends a task request to the cloud.

2. The cloud starts a task context associated with `T1`, performs planning for visitor reception, navigation, and subsequent delivery, and begins returning acknowledgment speech and status speech to the robot.

3. While the robot is speaking, the user interrupts again: “Do not go to the meeting room yet. First hand the document to Engineer Li near the entrance, and avoid the area near the elevator.”

4. After detecting the voice interruption, the robot edge side immediately stops current speech, clears the local speech buffer and pending playback queue, and enters `AwaitingResume(T1)`.

5. Because of network delay, subsequent speech previously generated by the cloud for `T1` continues to arrive at the robot edge side.  
   Based on the current locked state and the `turn_id` carried in the data, the robot identifies that the arriving speech belongs to prior turn `T1`, and directly discards it before queue admission so that it is not played.

6. The robot parses the new voice input into incremental constraints, including “change the delivery recipient to Engineer Li” and “add an avoid-the-elevator-area restriction,” and sends the constraints to the cloud.

7. The cloud preserves the original task context and does not terminate the original task instance. Instead, it updates the target recipient and path constraints based on the existing plan, generates a new turn `T2`, and sends a resume control message containing `parent_turn_id = T1`.

8. After verifying that the resume control message matches the currently locked turn, the robot edge side exits the locked state, allows speech output associated with `T2` into local playback, and continues executing the updated task.

---

## 8. Distinction from Existing Approaches / 与现有方案相比的区别

**中文**  
与常见的语音打断处理方案相比，本发明至少具有以下区别：

1. **不仅停止当前播放，而且阻断旧回合后续语音进入本地播放链路。**  
   本发明关注的是打断后仍可能继续到达的旧回合残余语音，并通过边缘侧回合校验在入队前完成隔离，而不是仅对已经开始播放的语音做停止处理。

2. **将语音交互打断与云端任务终止解耦。**  
   用户打断当前语音输出时，云端任务不必一并终止，更适合需要持续计算的人形机器人任务场景。

3. **支持在原任务上下文上进行增量修正。**  
   新的语音输入被解释为对原任务的约束更新，而不是简单触发一个全新的独立任务，从而减少重新规划的范围和代价。

4. **适用于存在网络时延和云边分工的人形机器人系统。**  
   本发明特别适合语音在本地输出而复杂任务在云端执行的系统架构。

**English**  
Compared with common voice interruption handling approaches, the invention differs at least in that:

1. **it not only stops current playback but also blocks subsequent prior-turn speech from entering the local playback path;**
2. **it decouples interruption of voice interaction from termination of the cloud task;**
3. **it supports incremental correction on top of the original task context;** and
4. **it is suitable for humanoid robot systems having network delay and cloud-edge functional separation.**

---

## 9. Technical Effects and Value / 技术效果与应用价值

**中文**  
本发明可以带来如下技术效果：

- 降低打断后旧语音误播的风险，提高语音交互可靠性；
- 减少因频繁打断而导致的云端任务重复中止和重启；
- 缩短用户修改指令后的重新响应时间；
- 提高人形机器人在复杂任务执行过程中的连续性和可控性；
- 更适合需要同时处理语音交互和长时任务执行的机器人应用。

本发明适用于具备语音交互能力、并采用云边协同架构的人形机器人。  
在不改变核心机制的前提下，该方案也可扩展应用于其他具备本地语音输出和远端任务执行能力的智能设备。

**English**  
The invention may provide the following technical effects:

- reducing the risk of stale speech being erroneously played after interruption, thereby improving reliability of voice interaction;
- reducing repeated termination and restart of cloud-side tasks caused by frequent interruptions;
- shortening response time after a user modifies an instruction;
- improving continuity and controllability of humanoid robots during execution of complex tasks; and
- better supporting robot applications that need to handle both voice interaction and long-running task execution.

The invention is applicable to humanoid robots having voice interaction capability and a cloud-edge collaborative architecture.  
Without changing the core mechanism, the approach may also be extended to other intelligent devices having local speech output and remote task execution capability.

---

## 10. Why SAP / 为什么与 SAP 相关

**中文**  
本发明与 SAP 的相关性主要体现在以下几个方面。

### （1）连接企业业务系统与物理执行环节

SAP 的核心优势在于对企业业务流程、主数据和执行数据的统一管理，例如仓储、制造、物流、现场服务和资产维护等场景。  
随着具身 AI 和机器人系统进入企业现场，机器人越来越可能成为企业流程在物理世界中的执行终端。  
在人形机器人执行接待、递送、巡检、搬运、辅助操作等任务时，其动作往往需要与 SAP 系统中的任务单、地点、对象、优先级和安全规则保持一致。  
本发明解决的正是在这种云边协同执行链路中，用户通过语音临时修改任务时，如何既避免旧语音误播，又不中断后端任务上下文的问题，因此与 SAP 的业务方向高度相关。

### （2）减少企业级任务被频繁中止和重建的代价

在 SAP 相关场景中，一个机器人任务背后往往不是单一步骤，而可能涉及多系统数据查询、任务编排、资源约束判断和流程联动。  
如果前端一次正常的语音打断就导致整个云端任务实例被销毁并重建，会带来额外的计算开销、系统抖动和响应延迟。  
本发明通过将“语音输出打断”与“云端任务终止”解耦，使机器人能够在保留原有任务上下文的基础上接受增量修正，这与 SAP 强调的流程连续性、执行稳定性和企业级可靠性一致。

### （3）适合 SAP 的业务场景落地

本发明适合应用于与 SAP 业务流程紧密结合的机器人场景，例如：

- 仓储与物流场景中，机器人根据语音修改取货点、交付点或避让区域；
- 制造或现场服务场景中，机器人根据操作员语音更新巡检顺序、目标设备或安全约束；
- 办公园区或前台接待场景中，机器人根据语音变更接待对象、递送对象或导航目的地。

这些场景的共同特点是：  
前端交互经常发生变化，但后端任务上下文不应被轻易清空。  
本发明正好提供了一种面向这类企业场景的交互与执行协同机制。

### （4）支持 SAP 在企业机器人与 AI agent 方向建立差异化能力

未来企业中的 AI 系统不仅要理解和建议，还要执行和协同执行。  
当 SAP 的 AI 能力进一步延伸到人形机器人、移动机器人或具备语音交互能力的现场终端时，系统必须处理一个关键问题：  
用户可以随时通过自然语言打断、修改和重定向任务，但企业级任务链路本身仍需要保持连续、可控和可追踪。  
本发明提供了一种兼顾自然语音交互体验与后端任务连续性的底层机制，有助于 SAP 在企业机器人和具身 AI 场景中形成区别于通用消费级助手的企业级能力。

**English**  
The relevance of this invention to SAP is reflected in at least the following aspects.

### (1) bridging enterprise systems and physical execution

SAP’s core strength lies in managing enterprise business processes, master data, and execution data across domains such as warehousing, manufacturing, logistics, field service, and asset maintenance.  
As embodied AI and robotic systems move into enterprise environments, robots are increasingly becoming physical execution endpoints of enterprise workflows.  
When a humanoid robot performs tasks such as reception, delivery, inspection, transport, or assisted operations, its actions often need to remain aligned with task orders, locations, objects, priorities, and safety rules maintained in SAP systems.  
This invention addresses exactly the issue that arises in such cloud-edge execution chains: when a user modifies a task through voice interruption, how to prevent stale speech from being played while preserving the backend task context.

### (2) reducing the cost of aborting and rebuilding enterprise-grade tasks

In SAP-related scenarios, a robot task is often not a single action, but part of a broader chain involving multi-system data access, task orchestration, resource constraints, and process dependencies.  
If a normal front-end voice interruption causes the cloud-side task instance to be destroyed and rebuilt from scratch, the result is additional compute overhead, system instability, and increased latency.  
By decoupling speech interruption from cloud task termination, the invention allows the robot to accept incremental corrections while preserving the original task context, which aligns closely with SAP’s emphasis on process continuity, execution stability, and enterprise-grade reliability.

### (3) strong fit with SAP application scenarios

The invention is well suited to robot scenarios tightly connected to SAP-driven business processes, for example:

- in warehousing and logistics, where a robot updates a pickup point, drop-off point, or avoidance area based on voice input;
- in manufacturing or field service, where a robot updates an inspection order, target equipment, or safety constraint based on operator speech; and
- in office campus or front-desk scenarios, where a robot changes a reception target, delivery recipient, or navigation destination based on voice input.

A common feature of these scenarios is that front-end interaction changes frequently while the backend task context should not be discarded lightly.  
This invention provides a coordination mechanism between interaction and execution that is well suited to such enterprise settings.

### (4) supporting differentiated capabilities for SAP in enterprise robotics and AI agents

Future enterprise AI systems will need not only to understand and recommend, but also to execute and coordinate execution.  
As SAP’s AI capabilities extend further into humanoid robots, mobile robots, and voice-enabled field devices, a key technical requirement emerges: users must be able to interrupt, modify, and redirect tasks through natural language while the enterprise task chain remains continuous, controllable, and traceable.  
This invention provides an underlying mechanism that balances natural voice interaction with backend task continuity and may help SAP build enterprise-grade capabilities differentiated from general consumer assistants.

---

## 11. ASCII Architecture Diagram / 架构图（ASCII）

### 11.1 Overall System Architecture / 总体架构图

```text
+----------------------------------------------------------------------------------+
|                           Humanoid Robot Voice Interaction System                |
+----------------------------------------------------------------------------------+

         User
          |
          | voice input / interruption
          v
+---------------------+         cloud-edge link         +--------------------------+
|  Robot Edge Side    | <-----------------------------> |       Cloud Side         |
|---------------------|                                 |--------------------------|
|  Mic / VAD          |                                 |  ASR / NLU / Planner     |
|  Interruption Det.  |                                 |  Task Orchestrator       |
|  Turn State Machine |                                 |  Context / Graph Executor|
|  Packet Validator   |                                 |  Constraint Updater      |
|  Queue Manager      |                                 |  TTS / Response Builder  |
|  Local TTS Player   |                                 |  Resume Controller       |
+---------------------+                                 +--------------------------+
          |                                                          |
          | local actuation / robot behavior                         |
          v                                                          v
+---------------------+                                 +--------------------------+
| Robot Motion / Task |                                 | Enterprise / SAP Systems |
| Execution Modules   |                                 | EWM / ERP / FSM / etc.   |
+---------------------+                                 +--------------------------+
```

### 11.2 Edge Internal Modules / 边缘侧内部模块图

```text
+------------------------------------------------------------------+
|                      Robot Edge Side                             |
+------------------------------------------------------------------+
|  [Voice Input]                                                   |
|      |                                                           |
|      v                                                           |
|  +-----------+      +------------------+                         |
|  | VAD /     | ---> | Interruption     |                         |
|  | Wakeword  |      | Detection        |                         |
|  +-----------+      +------------------+                         |
|                             |                                    |
|                             v                                    |
|                    +------------------+                          |
|                    | Turn State       |<-------------------+     |
|                    | Machine          |                    |     |
|                    +------------------+                    |     |
|                             |                              |     |
|                             v                              |     |
|                    +------------------+                    |     |
| cloud packet ----> | Packet Validator | ------------------+     |
|                    +------------------+                          |
|                             |                                    |
|                             v                                    |
|                    +------------------+                          |
|                    | Queue Manager    |                          |
|                    +------------------+                          |
|                             |                                    |
|                             v                                    |
|                    +------------------+                          |
|                    | Local TTS Player |                          |
|                    +------------------+                          |
+------------------------------------------------------------------+
```

### 11.3 Cloud Internal Modules / 云端内部模块图

```text
+--------------------------------------------------------------------------------+
|                                 Cloud Side                                     |
+--------------------------------------------------------------------------------+
|  +-------------+   +-------------+   +----------------+   +----------------+   |
|  | ASR / NLU   |-->| Task Intent |-->| Task Context   |-->| Planner /      |   |
|  | / Semantic  |   | Parser      |   | / Graph Exec   |   | Replanner      |   |
|  +-------------+   +-------------+   +----------------+   +----------------+   |
|                                                                   |            |
|                                                                   v            |
|                                                         +----------------+     |
|                                                         | Resume         |     |
|                                                         | Controller     |     |
|                                                         +----------------+     |
|                                                                   |            |
|                                                                   v            |
|                                                         +----------------+     |
|                                                         | TTS / Response |     |
|                                                         +----------------+     |
+--------------------------------------------------------------------------------+
                                    |
                                    v
                          +-----------------------+
                          | SAP / Enterprise APIs |
                          +-----------------------+
```

---

## 12. ASCII Sequence Diagram / 时序图（ASCII）

### 12.1 Main Interruption-and-Resume Flow / 主流程时序图

```text
User             Robot Edge                  Cloud                    SAP/Backend
 |                   |                         |                           |
 |-- Voice cmd T1 -->|                         |                           |
 |                   |-- Task request T1 ----->|---- query / planning ---->|
 |                   |                         |<--- data / task context ---|
 |                   |<-- speech/status T1 ----|                           |
 |<==== play T1 =====|                         |                           |
 |                   |                         |                           |
 |-- interrupt ----->|                         |                           |
 |                   | stop playback           |                           |
 |                   | clear queue/cache       |                           |
 |                   | lock on T1              |                           |
 |                   |                         |                           |
 |                   |<-- stale speech T1 -----|                           |
 |                   | drop before enqueue     |                           |
 |                   |                         |                           |
 |-- correction ---->|                         |                           |
 |                   |-- incremental update -->|---- partial replanning --->|
 |                   |                         |<--- updated result/context-|
 |                   |<-- resume ctrl T2 ------|                           |
 |                   | validate parent=T1      |                           |
 |                   | unlock                   |                           |
 |                   |<-- speech/status T2 ----|                           |
 |<==== play T2 =====|                         |                           |
 |                   |                         |                           |
```

### 12.2 Edge Drop Logic During Lock / 锁定期间旧包丢弃逻辑时序图

```text
Cloud                           Robot Edge
  |                                  |
  |-- speech packet(turn=T1) ------->|  state = AwaitingResume(T1)
  |                                  |  check turn_id == T1
  |                                  |  no resume authorization
  |                                  |  DROP
  |                                  |
  |-- speech packet(turn=T3) ------->|  state = AwaitingResume(T1)
  |                                  |  unmatched / unauthorized new turn
  |                                  |  DROP
  |                                  |
  |-- resume ctrl(T2,parent=T1) ---->|  state = AwaitingResume(T1)
  |                                  |  validate parent_turn_id == T1
  |                                  |  UNLOCK
  |                                  |
  |-- speech packet(turn=T2) ------->|  state = Active(T2)
  |                                  |  enqueue
  |                                  |  play
```

---

## 13. ASCII State Machine Diagram / 状态机图（ASCII）

```text
                           +------------------+
                           |      Idle        |
                           +------------------+
                                    |
                                    | receive/play turn Tn
                                    v
                           +------------------+
                           |    Active(Tn)    |
                           +------------------+
                                    |
                                    | user interruption
                                    v
                           +------------------+
                           |  Cancelled(Tn)   |
                           | stop + flush     |
                           +------------------+
                                    |
                                    | automatic transition
                                    v
                           +------------------+
                           | AwaitingResume   |
                           |      (Tn)        |
                           +------------------+
                             |       |       |
      stale speech(Tn) ------+       |       +------ unauthorized new turn --> DROP
                             |       |
                             |       +------ timeout / fail-safe --> remain locked
                             |
                             +------ resume ctrl(Tm,parent=Tn) valid
                                             |
                                             v
                                    +------------------+
                                    |    Active(Tm)    |
                                    +------------------+
```

---

## 14. Key Novelty Points for Review / 供内部评审快速抓重点的创新点

**中文**  
如果内部评审想快速看“到底新在哪里”，可以概括为以下四点：

1. **打断后不是简单 stop playback，而是进入与旧回合绑定的锁定状态；**
2. **锁定期间在边缘侧、入队前隔离旧回合残余语音；**
3. **用户语音打断不直接终止云端任务实例；**
4. **云端基于原任务上下文接收增量约束，并通过恢复控制消息完成新回合接管。**

**English**  
For quick internal review, the novelty may be summarized in four points:

1. after interruption, the system does not merely stop playback, but enters a locked state bound to the interrupted prior turn;
2. during the locked state, stale prior-turn speech is isolated at the edge side before queue admission;
3. a user voice interruption does not directly terminate the cloud task instance; and
4. the cloud accepts incremental constraints on top of the original task context and enables new-turn takeover through a resume control message.

---

## 15. Drafting Notes / 起草备注

**中文**  
后续如果交给外部专利律师，建议重点保护以下几个独立主线：

- 方法权利要求：  
  打断检测 → 停止并清空 → 锁定旧回合 → 入队前校验并丢弃旧语音 → 增量更新云端任务 → 恢复控制消息解锁 → 新回合接管输出。

- 系统权利要求：  
  人形机器人边缘侧模块 + 云端任务连续执行模块 + 恢复控制模块。

- 存储介质 / 软件权利要求：  
  由程序指令执行上述方法流程。

从属点可重点覆盖：

- `turn_id / parent_turn_id`
- `AwaitingResume` 锁定状态
- 恢复控制消息匹配规则
- 优先级队列、去重、失效标记
- 超时与 fail-safe
- 增量约束的形式和类型
- 与企业系统 / SAP 后端任务上下文的联动

**English**  
If this disclosure is later handed to outside patent counsel, the following lines are recommended for primary protection:

- method claim track:  
  interruption detection -> stop and flush -> lock prior turn -> validate and drop stale speech before queue admission -> incrementally update cloud task -> unlock via resume control message -> new-turn takeover;

- system claim track:  
  humanoid robot edge-side modules + cloud-side task continuity modules + resume control modules; and

- storage-medium / software claim track:  
  program instructions for causing the above method to be performed.

Recommended dependent points include:

- `turn_id / parent_turn_id`;
- `AwaitingResume` locked state;
- resume control matching rules;
- priority queue, deduplication, invalidation marking;
- timeout and fail-safe handling;
- forms and types of incremental constraints; and
- linkage with enterprise-system / SAP-backed task contexts.
