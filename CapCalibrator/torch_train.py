import torch
import argparse
from pathlib import Path
import logging
import time
import torch_src.torch_data as torch_data
import torch_src.torch_model as torch_model



def train_loop(opt):
    opt.is_train = True
    train_dataset = torch_data.MyDataLoader(opt)
    opt.is_train = False
    val_dataset = torch_data.MyDataLoader(opt)
    model = torch_model.MyModel(opt)
    # loss_fn = torch.nn.MSELoss()
    alpha = 0.7
    for epoch in range(opt.number_of_epochs):
        for batch_index, (input, target) in enumerate(train_dataset):
            model.optimizer.zero_grad()
            output_sensors, output_euler = model.network(input)
            train_loss_sensors = torch.mean(torch.linalg.norm(target["raw_projected_data"] - output_sensors, dim=2))
            train_loss_euler = torch.mean(torch.linalg.norm(target["rot_and_scale"] - output_euler, dim=1))
            train_loss = (1-alpha)*train_loss_sensors + alpha*train_loss_euler
            # train_loss = loss_fn(output, target["raw_projected_data"])
            logging.info("train: epoch: {}, batch {} / {}, loss: {}".format(epoch,
                                                                     batch_index,
                                                                     len(train_dataset) // opt.batch_size,
                                                                     train_loss.cpu().detach().numpy()))
            train_loss.backward()
            model.optimizer.step()
        model.save_network(which_epoch=str(epoch))
        model.save_network(which_epoch="latest")
        with torch.no_grad():
            val_loss_total = torch.zeros(1).to(opt.device)
            for input, target in val_dataset:
                model.optimizer.zero_grad()
                output_sensors, output_euler = model.network(input)
                val_loss_sensors = torch.mean(torch.linalg.norm(target["raw_projected_data"] - output_sensors, dim=2))
                val_loss_euler = torch.mean(torch.linalg.norm(target["rot_and_scale"] - output_euler, dim=1))
                val_loss = (1 - alpha) * val_loss_sensors + alpha * val_loss_euler
                # val_loss = loss_fn(output, target)
                val_loss_total += val_loss
            val_loss_total /= len(val_dataset)
            logging.info("validation: epoch: {}, loss: {}".format(epoch, val_loss_total.cpu().detach().numpy()))
        model.scheduler.step(val_loss)
        logging.info("lr: {}".format(model.optimizer.param_groups[0]['lr']))



def parse_arguments():
    parser = argparse.ArgumentParser(description='This script trains STORM-Net')
    parser.add_argument("experiment_name", help="The name to give the experiment")
    parser.add_argument("data_path", help="The path to the folder containing the synthetic data")
    parser.add_argument("--architecture", type=str, choices=["fc", "1dconv"], default="fc", help="Selects architecture")
    parser.add_argument("--gpu_ids", type=int, default=-1, help="Which GPU to use (or -1 for cpu)")
    parser.add_argument("--continue_train", action="store_true", help="continue from latest epoch")
    parser.add_argument("--batch_size", type=int, default=1, help="Batch size for training")
    parser.add_argument("--number_of_epochs", type=int, default=2000, help="Number of epochs for training loop")
    parser.add_argument("--lr", type=float, default=1e-4, help="learning rate for optimizer")
    parser.add_argument('--beta1', type=float, default=0.9, help='momentum term of adam')
    parser.add_argument("--template",
                        help="The template file path (given in space delimited csv format of size nx3). Required if mode is auto")
    parser.add_argument("--network_input_size", type=int, default=10, help="Input layer size for STORM-Net")
    parser.add_argument("--network_output_size", type=int, default=3, help="Output layer size for STORM-Net")
    parser.add_argument("--num_threads", type=int, default=0, help="Number of worker threads for dataloader")
    parser.add_argument("--log", action="store_true", help="If present, writes training log")
    parser.add_argument("--tensorboard",
                        help="If present, writes training stats to this path (readable with tensorboard)")
    parser.add_argument("-v", "--verbosity", type=str, choices=["debug", "info", "warning"], default="info", help="Selects verbosity level")
    # if len(sys.argv) == 1:
    #     parser.print_help(sys.stderr)
    #     sys.exit(1)
    # cmd = "test_torch ../../renders --template ../../example_models/example_model.txt".split()
    args = parser.parse_args()
    args.root = Path("runs", args.experiment_name)
    args.root.mkdir(parents=True, exist_ok=True)
    if args.log:
        args.log = Path(args.root, "log_{}".format(str(time.time())))
    if args.tensorboard:
        args.tensorboard = Path(args.tensorboard)
    args.data_path = Path(args.data_path)
    args.is_train = True
    if args.gpu_ids == -1:
        args.device = torch.device('cpu')
    else:
        args.device = torch.device('cuda:{}'.format(args.gpu_ids))
    return args


if __name__ == "__main__":
    opt = parse_arguments()
    if opt.log:
        logging.basicConfig(filename=opt.log, filemode='w', level=opt.verbosity.upper())
    else:
        logging.basicConfig(level=opt.verbosity.upper())
    logging.info("starting training loop.")
    train_loop(opt)
    logging.info("finished training.")
