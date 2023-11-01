import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

font = {'size': 30}

# 双星号传入map数值
plt.rc('font', **font)

# 开始预设node算法名称和作图名称
tolerance = "1e-05"
names = [
    "node",
    "anode",
    "sonode",
    "hbnode",
    "ghbnode",
    "pidnode",
    "gpidnode"
]
alt_names = [
    "NODE",
    "ANODE",
    "SONODE",
    "HBNODE",
    "GHBNODE",
    "PIDNODE",
    "GPIDNODE"
]
# gpidnode_file = "gpidnode_with_resnet_1e-05.csv"
df_names = {}
for name in names:
    # filepath = f"../imgdat/1_2/{name}_{tolerance}.csv"
    # if name != "gpidnode":
    filepath = f"C:/Users/29373/Desktop/NesterovNODE-main/NesterovNODE-main/mnist/imgdat/0_1/{name}_{tolerance}.csv"

    temp_df = pd.read_csv(filepath, header=None,
                          names=["model", "test#", "train/test", "iter", "loss", "acc", "forwardnfe", "backwardnfe",
                                 "time/iter", "time_elapsed", "gamma", "corr"])
    df_names[name] = temp_df
df_names[names[-1]].head()

# 预设画图的颜色，线条等
colors = [
    "mediumvioletred",
    "red",
    "deepskyblue",
    "royalblue",
    "navy",
    "green",
    "darkorange",
    "purple",
    "lightgreen"
]
line_styles = [
    ':',
    '--',
    '-.',
    '-.',
    '-.',
    '-',
    '-',
    '-*',
    '-*'
]
line_widths = [
    7,
    7,
    7,
    7,
    7,
    9,
    9,
    9,
    9
]

# 读取历史数据对于每一个模型进行nfe,acc,test loss等指标的构造 注意切片都是左闭右开的
fig = plt.figure(figsize=(26, 17))
gs = fig.add_gridspec(2, 6, hspace=0.25, wspace=1.2)
ax1 = fig.add_subplot(gs[0, :2])
ax2 = fig.add_subplot(gs[0, 2:4])
ax3 = fig.add_subplot(gs[0, 4:])
ax4 = fig.add_subplot(gs[1, 1:3])
ax6 = fig.add_subplot(gs[1, 3:5])
axes = (ax1, ax2, ax4)
height_width_ratio = "auto"
alt_attr_names = ["NFEs (forward)", "NFEs (backward)", "Loss"]
for j, attribute in enumerate(["forwardnfe", "backwardnfe", "loss"]):
    axes[j].set_aspect(height_width_ratio)
    for i, name in enumerate(names):
        # print(i, name)
        df_name = df_names[name]
        df_name_train = df_name.loc[df_name["train/test"] == "train"]
        attr_arr = df_name_train[attribute]
        iteration_arr = df_name_train["iter"]
        assert attr_arr.shape[0] <= 100  # max number of iterations
        axes[j].plot(iteration_arr, attr_arr, line_styles[i], linewidth=line_widths[i], color=colors[i],
                     label=alt_names[i])
    axes[j].set(xlabel="Epoch", ylabel=f"Train {alt_attr_names[j]}")
    axes[j].set_xlim(0, 40)
    # 对于指标展示图进行一定的坐标轴范围裁剪
    if attribute == "backwardnfe":
        axes[j].set_ylim([35, 100])
    if attribute == "forwardnfe":
        axes[j].set_ylim([20, 80])
    if attribute == "loss":
        axes[j].set_ylim(0.0, 0.85)
    axes[j].grid()
alt_attr_names = ["Accuracy", "NFEs (forward)"]
offset = 2
axes = (ax6, ax3)
for j, attribute in enumerate(["acc", "forwardnfe"]):
    axes[j].set_aspect(height_width_ratio)
    for i, name in enumerate(names):
        df_name = df_names[name]
        df_name_train = df_name.loc[df_name["train/test"] == "test"]
        attr_arr = df_name_train[attribute]
        iteration_arr = np.array(df_name_train["iter"])
        assert attr_arr.shape[0] <= 100  # max number of iterations
        # 需要对于测试精度进行特殊的处理
        # if attribute=="acc":
        #     log_itr_arr = np.log(iteration_arr)
        #     plt.xticks(log_itr_arr, [str(i) if i == 20 or i == 40 else "" for i in iteration_arr])
        #     axes[j].plot(log_itr_arr, attr_arr, line_styles[i], color=colors[i], linewidth=line_widths[i],
        #                  label=alt_names[i])
        # else:
        axes[j].plot(iteration_arr, attr_arr, line_styles[i], color=colors[i], linewidth=line_widths[i],
                     label=alt_names[i])
        # 对于测试精度需要专门做一个测试精度的对比 同时将对比的坐标系改成对数坐标形式 同时对于坐标数据图进行一定的网格裁剪
    axes[j].set(xlabel="Epoch", ylabel=f"Test {alt_attr_names[j]}")
    axes[j].set_xlim(0, 40)
    if attribute == "acc":
        axes[j].set_ylim(0.90, 0.99)
    if attribute == "forwardnfe":
        axes[j].set_ylim(30, 80)
    # plt.legend()
    axes[j].grid()
axbox = axes[0].get_position()
l5 = plt.legend(bbox_to_anchor=(0.5, axbox.y0 - 0.22), loc="lower center",
                bbox_transform=fig.transFigure, ncol=3)
# plt.savefig(f"result.pdf", transparent=True, bbox_inches='tight', pad_inches=0)
plt.savefig(f"mnist_result.jpg", transparent=True, bbox_inches='tight', pad_inches=0, dpi=500)
plt.show()

for i, name in enumerate(names):
    df_name = df_names[name]
    df_name_train = df_name.loc[df_name["train/test"] == "test"]
    attr_arr = df_name_train["acc"]
    print(f"Accuracy of {name}: {np.max(attr_arr)}")
