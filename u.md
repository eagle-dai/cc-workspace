# 下划线 math mode 测试

## A 原样行内

说清六件事： $H = (\text{asset}, \text{window}, \text{signal\_source}, \text{benchmark}, \text{metric}, \text{reject\_when})$ 。后文。

## B 行内改块级 $$

说清六件事：

$$H = (\text{asset}, \text{window}, \text{signal\_source}, \text{benchmark}, \text{metric}, \text{reject\_when})$$

## C 行内 + 下划线用 \text 内不转义（原始 _）

说清六件事： $H = (\text{asset}, \text{signal_source}, \text{reject_when})$ 。后文。

## D 行内短公式含 \_

值 $a\_b$ 结束。

## E 行内 P_{t} 下标（对照，本就正常）

价格 $P_{t}$ 是收盘价。
