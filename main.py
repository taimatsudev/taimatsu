'''Train MNIST with PyTorch.'''

import os
import argparse
import logging

import torchvision
from torchvision import transforms
import torch
from torch import nn
from torch import optim
from torch.backends import cudnn

from resnet import ResNet18
from utils import progress_bar

from torchswarm.rempso import RotatedEMParicleSwarmOptimizer
from nn_utils import CELoss, CELossWithPSO



if torch.cuda.is_available():
    print("Using GPU...")
    DEVICE = 'cuda'
else:
    print("Using CPU...")
    DEVICE = 'cpu'

# pylint: disable=R0914,R0915,C0116
def run():
    print('in run function')

    parser = argparse.ArgumentParser(description='PyTorch MNIST Training')
    parser.add_argument('--lr', default=0.1, type=float, help='learning rate')
    parser.add_argument('--resume', '-r', action='store_true',
                        help='resume from checkpoint')
    args = parser.parse_args()

    start_epoch = 0  # start from epoch 0 or last checkpoint epoch
    batch_size = 125
    swarm_size = 10

    # Data
    print('==> Preparing data..')
    transform_train = transforms.Compose([
        transforms.RandomCrop(28, padding=4),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize((0.5,), (0.5,))
        # transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2023, 0.1994, 0.2010)),
    ])

    transform_test = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.5,), (0.5,)),
        # transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2023, 0.1994, 0.2010)),
    ])

    trainset = torchvision.datasets.MNIST(
        root='./data', train=True, download=True, transform=transform_train)
    trainloader = torch.utils.data.DataLoader(
        trainset, batch_size=125, shuffle=True, num_workers=2)

    testset = torchvision.datasets.MNIST(
        root='./data', train=False, download=True, transform=transform_test)
    testloader = torch.utils.data.DataLoader(
        testset, batch_size=100, shuffle=False, num_workers=2)

    # Model
    print('==> Building model..')
    net = ResNet18(1)
    net = net.to(DEVICE)
    if DEVICE == 'cuda':
        net = torch.nn.DataParallel(net)
        cudnn.benchmark = True

    if args.resume:
        # Load checkpoint.
        print('==> Resuming from checkpoint..')
        assert os.path.isdir('checkpoint'), 'Error: no checkpoint directory found!'
        checkpoint = torch.load('./checkpoint/ckpt.pth')
        net.load_state_dict(checkpoint['net'])
        start_epoch = checkpoint['epoch']

    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(net.parameters(), lr=args.lr)
    approx_criterion = CELossWithPSO.apply

    # Training
    def train(epoch):
        print(f'\nEpoch: {epoch}')
        net.train()
        train_loss = 0
        correct = 0
        total = 0
        for batch_idx, (inputs, targets) in enumerate(trainloader):
            inputs, targets = inputs.to(DEVICE), targets.to(DEVICE)
            logging.debug("targets: %s", targets)
            targets.requires_grad = False
            print("PSO ran...")
            particle_swarm_optimizer = RotatedEMParicleSwarmOptimizer(batch_size,
                                                                      swarm_size, 10, targets)
            particle_swarm_optimizer.optimize(CELoss(targets))
            for _ in range(5):
                c1r1, c2r2, gbest = particle_swarm_optimizer.run_one_iter(verbosity=False)
            optimizer.zero_grad()
            outputs = net(inputs)
            logging.debug("gbest: %s", gbest)
            loss = approx_criterion(outputs, targets, c1r1+c2r2, 0.4, gbest)
            loss.backward()
            optimizer.step()
            print(loss.item(), c1r1+c2r2)
            train_loss += loss.item()
            _, predicted = outputs.max(1)
            total += targets.size(0)
            correct += predicted.eq(targets).sum().item()

            print_output = f"""Loss: {train_loss/(batch_idx+1):3f}
                    | Acc: {100.*correct/total}%% ({correct/total})"""

            print(batch_idx, len(trainloader), print_output)
            progress_bar(batch_idx, len(trainloader), print_output)

    def test(epoch):
        net.eval()
        test_loss = 0
        correct = 0
        total = 0
        with torch.no_grad():
            for batch_idx, (inputs, targets) in enumerate(testloader):
                inputs, targets = inputs.to(DEVICE), targets.to(DEVICE)
                outputs = net(inputs)
                loss = criterion(outputs, targets)

                test_loss += loss.item()
                _, predicted = outputs.max(1)
                total += targets.size(0)
                correct += predicted.eq(targets).sum().item()

                progress_bar(batch_idx,
                    len(testloader),
                    f"""Loss: {test_loss/(batch_idx+1):3f}
                    | Acc: {100.*correct/total}%% ({correct/total})""")

        # Save checkpoint.
        acc = 100.*correct/total

        print('Saving..')
        state = {
            'net': net.state_dict(),
            'acc': acc,
            'epoch': epoch,
        }
        if not os.path.isdir('checkpoint'):
            os.mkdir('checkpoint')
        torch.save(state, './checkpoint/ckpt.pth')

    for epoch in range(start_epoch, start_epoch+200):
        train(epoch)
        test(epoch)

if __name__ == '__main__':
    run()