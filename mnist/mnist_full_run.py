from os import path
import sys

sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))
import argparse
import csv

from anode_data_loader import mnist
from base import *
from mnist.mnist_train import train

parser = argparse.ArgumentParser()
parser.add_argument('--tol', type=float, default=1e-5)
parser.add_argument('--adjoint', type=eval, default=True)
parser.add_argument('--visualize', type=eval, default=True)
parser.add_argument('--niters', type=int, default=40)
parser.add_argument('--lr', type=float, default=0.001)
parser.add_argument('--gpu', type=int, default=0)
parser.add_argument('--timeout', type=int, default=10000, help='Maximum time/iter to do early dropping')
parser.add_argument('--nfe-timeout', type=int, default=300,
                    help='Maximum nfe (forward or backward) to do early dropping')
parser.add_argument('--names', nargs='+', default=['hbnode'],
                    help="List of models to run")
parser.add_argument('--log-file', default="outdat1", help="name of the logging csv file")
parser.add_argument('--no-run', action="store_true", help="To not run the training procedure")
parser.add_argument('--batch-size', type=int, default=64)

# regarding the generic input parameters of the pidnode.
parser.add_argument('--pid-general-type', type=int, default=3)
# temporary addition of the pidnode parameter input.
parser.add_argument('--kp', type=float, default=2.)
parser.add_argument('--ki', type=float, default=2.)
parser.add_argument('--kd', type=float, default=1.5)
args = parser.parse_args()

torch.autograd.set_detect_anomaly(True)


# shape: [time, batch, derivatives, channel, x, y]


class anode_initial_velocity(nn.Module):

    def __init__(self, in_channels, aug, dch=1):
        super(anode_initial_velocity, self).__init__()
        self.aug = aug
        self.in_channels = in_channels
        self.dch = dch

    def forward(self, x0):
        outshape = list(x0.shape)
        outshape[1] = self.aug * self.dch
        out = torch.zeros(outshape).to(args.gpu)
        out[:, :1] += x0
        out = rearrange(out, 'b (d c) ... -> b d c ...', d=self.dch)
        return out


class hbnode_initial_velocity(nn.Module):

    def __init__(self, in_channels, out_channels, nhid):
        super(hbnode_initial_velocity, self).__init__()
        assert (3 * out_channels >= in_channels)
        self.actv = nn.LeakyReLU(0.3)
        self.fc1 = nn.Conv2d(in_channels, nhid, kernel_size=1, padding=0)
        self.fc2 = nn.Conv2d(nhid, nhid, kernel_size=3, padding=1)
        self.fc3 = nn.Conv2d(nhid, 2 * out_channels - in_channels, kernel_size=1, padding=0)
        self.out_channels = out_channels
        self.in_channels = in_channels

    def forward(self, x0):
        x0 = x0.float()
        out = self.fc1(x0)
        out = self.actv(out)
        out = self.fc2(out)
        out = self.actv(out)
        out = self.fc3(out)
        out = torch.cat([x0, out], dim=1)
        out = rearrange(out, 'b (d c) ... -> b d c ...', d=2)
        return out


class pidnode_initial_velocity(nn.Module):

    def __init__(self, in_channels, out_channels, nhid, gpu=0):
        super(pidnode_initial_velocity, self).__init__()
        assert (3 * out_channels >= in_channels)
        self.actv = nn.LeakyReLU(0.3)
        self.fc1 = nn.Conv2d(in_channels, nhid, kernel_size=1, padding=0)
        self.fc2 = nn.Conv2d(nhid, nhid, kernel_size=3, padding=1)
        self.fc3 = nn.Conv2d(nhid, 2 * out_channels - in_channels, kernel_size=1, padding=0)
        self.out_channels = out_channels
        self.in_channels = in_channels
        self.gpu = gpu

    def forward(self, x0):
        x0 = x0.float()
        out = self.fc1(x0)
        out = self.actv(out)
        out = self.fc2(out)
        out = self.actv(out)
        out = self.fc3(out)
        # out_v = out * out
        # 扩展对应的通道，然后做三个变量 h m v的拆分
        # import pdb; pdb.set_trace()
        batch_size, channels, height, width = x0.shape
        v0 = torch.zeros(batch_size, self.out_channels, height, width).to(self.gpu)
        out = torch.cat([x0, out, v0], dim=1)
        out = rearrange(out, 'b (d c) ... -> b d c ...', d=3)
        # import pdb; pdb.set_trace()
        return out


class DF(nn.Module):

    def __init__(self, in_channels, nhid, out_channels=None):
        super(DF, self).__init__()
        if out_channels is None:
            out_channels = in_channels
        self.activation = nn.ReLU(inplace=True)
        self.fc1 = nn.Conv2d(in_channels + 1, nhid, kernel_size=1, padding=0)
        self.fc2 = nn.Conv2d(nhid + 1, nhid, kernel_size=3, padding=1)
        self.fc3 = nn.Conv2d(nhid + 1, out_channels, kernel_size=1, padding=0)

    def forward(self, t, x0):
        x0 = rearrange(x0, 'b d c x y -> b (d c) x y')
        t_img = torch.ones_like(x0[:, :1, :, :]).to(device=args.gpu) * t
        out = torch.cat([x0, t_img], dim=1)
        out = self.fc1(out)
        out = self.activation(out)
        out = torch.cat([out, t_img], dim=1)
        out = self.fc2(out)
        out = self.activation(out)
        out = torch.cat([out, t_img], dim=1)
        out = self.fc3(out)
        out = rearrange(out, 'b c x y -> b 1 c x y')
        return out


class predictionlayer(nn.Module):
    def __init__(self, in_channels, truncate=False, dropout=0.0):
        super(predictionlayer, self).__init__()
        self.dense = nn.Linear(in_channels * 28 * 28, 10)
        self.truncate = truncate
        self.dropout = nn.Dropout(dropout)

    def forward(self, x):
        if self.truncate:
            x = rearrange(x[:, 0], 'b ... -> b (...)')
        else:
            x = rearrange(x, 'b ... -> b (...)')
        x = self.dropout(x)
        x = self.dense(x)
        return x


class tvSequential(nn.Sequential):
    def __init__(self, ic, layer, predict):
        super(tvSequential, self).__init__(ic, layer, predict)
        self.ic = ic
        self.layer = layer
        self.predict = predict

    def forward(self, x):
        x = self.ic(x)
        x, rec = self.layer(x)
        out = self.predict(x)
        return out, rec


trdat, tsdat = mnist(batch_size=args.batch_size, path_to_data='./mnist_data')

tanh = nn.Tanh()
hard_tanh_half = nn.Hardtanh(-0.5, 0.5)


def model_gen(name, gpu, **kwargs):
    if name == 'node':
        dim = 1
        nhid = 92
        evaluation_times = torch.Tensor([1, 2]).to(device=gpu)
        layer = NODElayer(NODE(DF(dim, nhid)), time_requires_grad=False, evaluation_times=evaluation_times, **kwargs)
        model = nn.Sequential(anode_initial_velocity(1, dim),
                              layer, predictionlayer(dim))
    elif name == 'anode':
        dim = 6
        nhid = 64
        evaluation_times = torch.Tensor([1, 2]).to(device=gpu)
        layer = NODElayer(NODE(DF(dim, nhid)), time_requires_grad=False, evaluation_times=evaluation_times, **kwargs)
        model = nn.Sequential(anode_initial_velocity(1, dim),
                              layer, predictionlayer(dim))
    elif name == 'sonode-':
        dim = 1
        nhid = 65
        evaluation_times = torch.Tensor([1, 2]).to(device=gpu)
        hblayer = NODElayer(SONODE(DF(2 * dim, nhid, dim)), time_requires_grad=False, evaluation_times=evaluation_times,
                            **kwargs)
        model = nn.Sequential(hbnode_initial_velocity(1, dim, nhid),
                              hblayer, predictionlayer(dim, truncate=True))
    elif name == 'sonode':
        dim = 5
        nhid = 50
        evaluation_times = torch.Tensor([1, 2]).to(device=gpu)
        hblayer = NODElayer(SONODE(DF(2 * dim, nhid, dim)), time_requires_grad=False, evaluation_times=evaluation_times,
                            **kwargs)
        model = nn.Sequential(hbnode_initial_velocity(1, dim, nhid),
                              hblayer, predictionlayer(dim, truncate=True))
    elif name == 'hbnode':
        dim = 5
        nhid = 50
        evaluation_times = torch.Tensor([1, 2]).to(device=gpu)
        layer = NODElayer(HeavyBallNODE(DF(dim, nhid), None), time_requires_grad=False,
                          evaluation_times=evaluation_times, **kwargs)
        model = nn.Sequential(hbnode_initial_velocity(1, dim, nhid),
                              layer, predictionlayer(dim, truncate=True))
    elif name == 'ghbnode':
        dim = 5
        nhid = 50
        evaluation_times = torch.Tensor([1, 2]).to(device=gpu)
        layer = NODElayer(HeavyBallNODE(DF(dim, nhid), actv_h=nn.Tanh(), corr=2.0, corrf=False),
                          time_requires_grad=False, evaluation_times=evaluation_times, **kwargs)
        model = nn.Sequential(hbnode_initial_velocity(1, dim, nhid),
                              layer, predictionlayer(dim, truncate=True))
    elif name == 'pidnode':
        dim = 5
        nhid = 49
        evaluation_times = torch.Tensor([1, 2]).to(device=gpu)
        layer = NODElayer(PIDNODE(DF(dim, nhid), None, sign=-1, ki=args.ki, kp=args.kp, kd=args.kd),
                          nesterov_algebraic=False,
                          time_requires_grad=False, evaluation_times=evaluation_times, **kwargs)
        model = nn.Sequential(pidnode_initial_velocity(1, dim, nhid),
                              layer, predictionlayer(dim, truncate=True)).to(device=args.gpu)
    elif name == 'gpidnode':
        dim = 5
        nhid = 49
        evaluation_times = torch.Tensor([1, 2]).to(device=gpu)
        layer = NODElayer(PIDNODE(DF(dim, nhid), sign=-1, actv_h=hard_tanh_half, actv_df=hard_tanh_half, ki=args.ki,
                                    kp=args.kp, kd=args.kd, corr=2.0, corrf=False, general_type=args.pid_general_type),
                          nesterov_algebraic=False, time_requires_grad=False,
                          evaluation_times=evaluation_times, **kwargs)
        model = nn.Sequential(pidnode_initial_velocity(1, dim, nhid),
                              layer, predictionlayer(dim, truncate=True)).to(device=args.gpu)
    else:
        print('model {} not supported.'.format(name))
        model = None
    gpu = torch.device(f"cuda:{gpu}")
    print(gpu)
    return model.to(gpu)


if __name__ == '__main__':
    rec_names = ["model", "test#", "train/test", "iter", "loss", "acc", "forwardnfe", "backwardnfe", "time/iter",
                 "time_elapsed"]
    csvfile = open(f'./imgdat/outdat0.csv', 'w')
    writer = csv.writer(csvfile)
    writer.writerow(rec_names)
    csvfile.close()

    dat = []
    for name in args.names:
        runnum = name[:3]
        if not args.no_run:
            log = open('./output/mnist/log_{}.txt'.format(runnum), 'w')
            datfile = open('./output/mnist/mnist_dat_{}_{}.txt'.format(runnum, args.tol), 'wb')
            # build the whole model
        model = model_gen(name, tol=args.tol, gpu=args.gpu)
        print(name, count_parameters(model), *[count_parameters(i) for i in model])
        optimizer = optim.Adam(model.parameters(), lr=args.lr / 2, weight_decay=0.000)
        lrscheduler = torch.optim.lr_scheduler.StepLR(optimizer, 200, 0.9)
        # train_out = train(model, optimizer, trdat, tsdat, args, evalfreq=1)

        if not args.no_run:
            evaluation_times_folder = "1_2"
            train_out = train(model, optimizer, trdat, tsdat, args, name, 0, evalfreq=1,
                              csvname=f'imgdat/{evaluation_times_folder}/{args.log_file}_{args.tol}.csv')
            # train_out = train(model, optimizer, trdat, tsdat, args, name, 0, evalfreq=1)
            dat.append([name, 0, train_out])
            log.writelines(['\n'] * 5)
            pickle.dump(dat, datfile)
            log.close()
            datfile.close()
