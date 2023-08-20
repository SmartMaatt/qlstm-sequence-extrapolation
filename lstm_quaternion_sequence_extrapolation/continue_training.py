import os
import time
import torch
import torch.nn as nn
import numpy as np
from torch.utils.data import DataLoader, random_split
from torch.utils.tensorboard import SummaryWriter

import recurrent_models as rm
from dataset_initializer import RotationDataset
from utilities import *


def continue_training(
        input_size = 4,             # Quaternion
        sequence_length = 100,      # Frames
        num_layers = 2, 

        hidden_size = 128, 
        num_classes = 4, 
        num_epochs = 4, 
        batch_size = 10, 
        learning_rate = 0.001, 
        previous_epochs = 3,
        checkpoint_interval = 2, 

        model_type = ModelType.LSTM,
        is_qal_loss = True, 
        show_evaluation = False, 

        model_dir = rf"./models",
        training_path = r"./data/mockup/large/training_data.csv",
        labels_path = r"./data/mockup/large/labels_data.csv"
):
    # Random seed configuration
    torch.manual_seed(303)

    # Device configuration
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print("\n>>> Continue training procedure started <<<")

    # File name configuration
    model_name = ""
    if model_type == ModelType.LSTM:
        model_name = "LSTM"
    elif model_type == ModelType.QLSTM:
        model_name = "QLSTM"
    elif model_type == ModelType.VectorizedQLSTM:
        model_name = "VectorizedQLSTM"

    loss_name = ""
    if is_qal_loss:
        loss_name = "qal"
    else:
        loss_name = "mse"

    # Check for files
    if not os.path.exists(rf"{model_dir}/{generate_model_file_name(model_name, loss_name, previous_epochs)}.pth"):
        print(f"Model file does not exist: {model_dir}/{generate_model_file_name(model_name, loss_name, previous_epochs)}.pth")
        return

    if not os.path.exists(rf"{model_dir}/{generate_model_file_name(model_name, loss_name, previous_epochs)}.opt"):
        print(f"Optimizer file does not exist: {model_dir}/{generate_model_file_name(model_name, loss_name, previous_epochs)}.opt")
        return
    print(f"Training model: {model_dir}/{generate_model_file_name(model_name, loss_name, previous_epochs)}.pth")

    
    # 1. Creating dataset
    print("\n1. Creating dataset")
    dataset = RotationDataset(training_path, labels_path, input_size, sequence_length)


    # 2. Splitting dataset
    print("\n2. Splitting dataset")
    training_size = int(0.8 * len(dataset))
    test_size = len(dataset) - training_size
    training_dataset, test_dataset = random_split(dataset, [training_size, test_size])


    # 3. Generating DataLoaders
    print("3. Generating DataLoaders")
    train_loader = DataLoader(dataset=training_dataset, batch_size=batch_size)
    test_loader = DataLoader(dataset=test_dataset, batch_size=batch_size)


    # 4. Creating model
    print("4. Creating model")
    if model_type == ModelType.LSTM:
        print(f"Model: LSTM")
        model = rm.LSTM(input_size, hidden_size, num_layers, num_classes, device).to(device)

    elif model_type == ModelType.QLSTM:
        print(f"Model: QLSTM")
        model = rm.StackedQLSTM(input_size, hidden_size, num_layers, batch_first=True, device=device).to(device)

    elif model_type == ModelType.VectorizedQLSTM:
        print(f"Model: Vectorized QLSTM")
        model = rm.VectorizedStackedQLSTM(input_size, hidden_size, num_layers, batch_first=True, device=device).to(device)

    else:
        print("Incorrect model type!")
        return

    print(f"Path: {model_dir}/{generate_model_file_name(model_name, loss_name, num_epochs)}")

    # Tensorboard
    writer = SummaryWriter(f"runs/{model_name}_{loss_name}")

    print(f"Sequence length: {sequence_length}")
    print(f"Layers: {num_layers}")
    print(f"Hidden size: {hidden_size}")
    print(f"Epochs: {num_epochs}")
    print(f"Batch size: {batch_size}")


    # 5. Loss and optimizer
    print("\n5. Creating criterion and optimizer")
    if is_qal_loss:
        print("Training criterion: QALLoss function")
        criterion = rm.QALLoss()
    else:
        print("Training criterion: MSELoss function")
        criterion = nn.MSELoss()

    print("Evaluation criterion: QALLoss function")
    criterion_eval = rm.QALLoss()

    print("Optimizer: Adam")
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    print(f"Learning rate: {learning_rate}")


    # 6. Load model and optimizer state data
    print("\n6. Load model and optimizer state data")
    try:
        model.load_state_dict(torch.load(rf"{model_dir}/{generate_model_file_name(model_name, loss_name, previous_epochs)}.pth"))
        optimizer.load_state_dict(torch.load(rf"{model_dir}/{generate_model_file_name(model_name, loss_name, previous_epochs)}.opt"))
    except FileNotFoundError as ex:
        print(f"File error: {ex}")
        return
    print("State data load completed")


    # 7. Training loop
    print("\n7. Starting training loop")
    n_total_steps = len(train_loader)
    running_loss = 0.0
    start_time = time.time()

    model.train()
    for epoch in range(num_epochs - previous_epochs):
        for i, (rotations, labels) in enumerate(train_loader):
            rotations = rotations.to(device)
            labels = labels.to(device)
            labels = labels.reshape(labels.shape[0], 4)

            # Forward
            outputs = model(rotations)
            loss = criterion(outputs, labels)
            
            # Backward
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            running_loss += loss.item()

            if (i+1) % 100 == 0:
                print(f'epoch {epoch + previous_epochs + 1} / {num_epochs}, step {i+1} / {n_total_steps}, loss {loss.item():.7f}, time: {(time.time() - start_time):.2f}s')
                # Tensorboard
                writer.add_scalar('training loss', running_loss / 100, (epoch + previous_epochs) * n_total_steps + i)
                running_loss = 0.0
        
        # Saving checkpoints
        if (epoch + previous_epochs + 1) % checkpoint_interval == 0:
            torch.save(model.state_dict(), rf"{model_dir}/{generate_model_file_name(model_name, loss_name, epoch + previous_epochs + 1)}.pth")
            torch.save(optimizer.state_dict(), rf"{model_dir}/{generate_model_file_name(model_name, loss_name, epoch + previous_epochs + 1)}.opt")
            print(f"Checkpoint for {generate_model_file_name(model_name, loss_name, epoch + previous_epochs + 1)} done")

    print(f"Learning took {seconds_to_hms(time.time() - start_time)}, [{(time.time() - start_time):.2f}s]")


    # 8. Test and evaluation
    print("\n8. Starting evaluation")
    model.eval()
    with torch.no_grad():
        test_loss = []
        n_samples = 0

        for (rotations, labels) in test_loader:
            rotations = rotations.to(device)
            labels = labels.to(device)
            labels = labels.reshape(labels.shape[0], input_size)
            output = model(rotations)

            test_loss.append(criterion_eval(output, labels).item())

            # Show evaluation results
            if show_evaluation:
                output = output.tolist()
                labels = labels.tolist()
                n_samples += 1

                for i in range(len(labels)):
                    print(f"output: {output[i]}, expected: {labels[i]}")
                print(f"loss: {test_loss[n_samples - 1]}")

        test_loss = np.array(test_loss)
        loss_mean = np.mean(test_loss)
        loss_std = np.std(test_loss)
        print(f'Loss mean: {loss_mean:.7f}, loss std: {loss_std:.7f}')


    # 9. Saving model
    print("\n9. Saving model")
    torch.save(model.state_dict(), rf"{model_dir}/{generate_model_file_name(model_name, loss_name, num_epochs)}.pth")
    torch.save(optimizer.state_dict(), rf"{model_dir}/{generate_model_file_name(model_name, loss_name, num_epochs)}.opt")
    print("Saving successed")


if __name__ == "__main__":
    # model_path = rf"./models/lstm_mse_batch10_epochs3.pth"
    # model_path = rf"./models/lstm_qal_batch10_epochs3.pth"
    # model_path = rf"./models/qlstm_mse_batch10_epochs3.pth"
    # model_path = rf"./models/qlstm_qal_batch10_epochs3.pth"
    # model_path = rf"./models/VectorizedQLSTM_mse_batch10_epochs3.pth"
    # model_path = rf"./models/VectorizedQLSTM_qal_batch10_epochs3.pth"

    # training_path = r"./data/mockup/training_data (Medium).csv"
    # labels_path = r"./data/mockup/labels_data (Medium).csv"
    training_path = r"./data/mockup/large/training_data.csv"
    labels_path = r"./data/mockup/large/labels_data.csv"

    input_size = 4             # Quaternion
    sequence_length = 100      # Frames
    num_layers = 2
    
    hidden_size = 128 
    num_classes = 4
    num_epochs = 15
    batch_size = 10 
    learning_rate = 0.001 
    previous_epochs = 10
    checkpoint_interval = 1

    show_evaluation = False 
    model_dir = rf"./models"
    
    def execute_continue_training(model_type:ModelType, is_qal_loss:bool):
        continue_training(
            input_size = input_size,
            sequence_length = sequence_length,
            num_layers = num_layers,

            hidden_size = hidden_size,
            num_classes = num_classes,
            num_epochs = num_epochs,
            batch_size = batch_size,
            learning_rate = learning_rate,
            previous_epochs = previous_epochs,
            checkpoint_interval = checkpoint_interval,

            model_type = model_type,
            is_qal_loss = is_qal_loss,
            show_evaluation = show_evaluation,

            model_dir = model_dir,
            training_path = training_path,
            labels_path = labels_path
        )

    # Execute queued training
    execute_continue_training(ModelType.LSTM, False)            # LSTM MSE
    execute_continue_training(ModelType.LSTM, True)             # LSTM QAL
    # execute_continue_training(ModelType.QLSTM, False)           # QLSTM MSE
    # execute_continue_training(ModelType.QLSTM, True)            # QLSTM QAL
    # execute_continue_training(ModelType.VectorizedQLSTM, False)  # Vectorized QLSTM MSE
    # execute_continue_training(ModelType.VectorizedQLSTM, True)   # Vectorized QLSTM MSE