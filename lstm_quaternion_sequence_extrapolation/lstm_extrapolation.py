import csv
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader, random_split

# Device configuration
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print("Program started")

# Hyper parameters
input_size = 4          # Quaternion
sequence_length = 100   # Frames
num_layers = 2

hidden_size = 128
num_classes = 4
num_epochs = 3
batch_size = 10
learning_rate = 0.001



# ===>>> Classes <<<===
# Rotation dataset
class RotationDataset(Dataset):
    def __init__(self, training_path, labels_path):
        super(RotationDataset, self).__init__()
        self.training_path = training_path
        self.labels_path = labels_path

        self.training_data = self._read_dataset(training_path)
        self.labels_data = self._read_dataset(labels_path)

        self.training_data = self._prepare_training_dataset(self.training_data)
        self.labels_data = self._prepare_labels_dataset(self.labels_data)
        self.n_samples = self.training_data.size()[0]
    
    def __getitem__(self, index):
        return self.training_data[index], self.labels_data[index]
    
    def __len__(self):
        return self.n_samples

    def _read_dataset(self, file_path: str):
        print(f"Reading: {file_path}")
        data = []
        with open(file_path, 'r') as file:
            reader = csv.reader(file)
            for row in reader:
                data.append(row)

        data = [x[1:] for x in data]
        data = [[float(y) for y in x] for x in data]
        return data

    def _prepare_training_dataset(self, data):
        final_data = []
        for i in range(int(len(data) / input_size)):
            sequence = []
            for j in range(sequence_length):
                sequence.append([data[i][j], data[i+1][j], data[i+2][j], data[i+3][j]])
            final_data.append(sequence)
        
        #return final_data
        return torch.tensor(final_data)
    
    def _prepare_labels_dataset(self, data):
        final_data = []
        for i in range(int(len(data) / input_size)):
            sequence = []
            sequence.append([data[i][0], data[i+1][0], data[i+2][0], data[i+3][0]])
            final_data.append(sequence)
        
        #return final_data
        return torch.tensor(final_data)

class LSTM(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers, num_classes):
        super(LSTM, self).__init__()
        self.num_layers = num_layers
        self.hidden_size = hidden_size
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True) # batch_first -> (batch_size, seq, input_size)
        self.fc = nn.Linear(hidden_size, num_classes)

    def forward(self, x):
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(device)
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(device)

        out, _ = self.lstm(x, (h0, c0))     # out: (batch_size, seq_len, hidden_size)
        out = out[:, -1, :]                 # out: [Sentiment classification!]
        out = self.fc(out)
        return out



# ===>>> Temporary testing functions <<<===
def predict():
    file_path = r"./data/mockup/training_data — kopia.csv"
    labels_path = r"./data/mockup/labels_data — kopia.csv"
    data = []
    with open(file_path, 'r') as file:
        reader = csv.reader(file)
        for row in reader:
            data.append(row)

        data = [x[1:] for x in data]
        data = [[float(y) for y in x] for x in data]

    final_data = []
    for i in range(int(len(data) / input_size)):
        sequence = []
        for j in range(sequence_length):
            sequence.append([data[i][j], data[i+1][j], data[i+2][j], data[i+3][j]])
        final_data.append(sequence)

    labels = []
    with open(labels_path, 'r') as file:
        reader = csv.reader(file)
        for row in reader:
            labels.append(row)

        labels = [x[1:] for x in labels]
        labels = [[float(y) for y in x] for x in labels]

    final_labels = []
    for i in range(int(len(labels) / input_size)):
        sequence = []
        sequence.append([labels[i][0], labels[i+1][0], labels[i+2][0], labels[i+3][0]])
        final_labels.append(sequence)

    with torch.no_grad():
        data = torch.tensor(final_data).to(device)
        l_tensor = torch.tensor(final_labels).to(device)
        l_tensor = l_tensor.reshape(l_tensor.shape[0], 4)

        output = model(data)
        output_list = output.tolist()
        # Zaokrąglenie wartości do 5 miejsc po przecinku
        rounded_list = [[round(x, 5) for x in q] for q in output_list]
        loss = criterion(output, l_tensor)
        print(f"result: {rounded_list}, loss: {loss.item():.7f}")



# 1. Creating dataset
print("1. Creating dataset")
training_path = r"./data/mockup/training_data.csv"
labels_path = r"./data/mockup/labels_data.csv"
dataset = RotationDataset(training_path, labels_path)

# 2. Splitting dataset
print("2. Splitting dataset")
training_size = int(0.8 * len(dataset))
test_size = len(dataset) - training_size
training_dataset, test_dataset = random_split(dataset, [training_size, test_size])

# 3. Generating DataLoaders
print("3. Generating DataLoaders")
train_loader = DataLoader(dataset=training_dataset, batch_size=batch_size)
test_loader = DataLoader(dataset=test_dataset, batch_size=batch_size)

# 4. Creating model
print("4. Creating model")
model = LSTM(input_size, hidden_size, num_layers, num_classes).to(device)

# 5. Loss and optimizer
print("5. Creating criterion and optimizer")
criterion = nn.MSELoss()
optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
predict()

# 6. Training loop
print("6. Starting training loop")
n_total_steps = len(train_loader)
for epoch in range(num_epochs):
    for i, (rotations, labels) in enumerate(train_loader):
        rotations = rotations.to(device)
        labels = labels.to(device)
        labels = labels.reshape(labels.shape[0], 4)

        # Forward
        outputs = model(rotations)
        loss = criterion(outputs, labels)

        # Backwards
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        if (i+1) % 10 == 0:
            print(f'epoch {epoch+1} / {num_epochs}, step {i+1} / {n_total_steps}, loss {loss.item():.7f}')

# 7. Test and evaluation
print("7. Starting evaluation")
with torch.no_grad():
    test_loss = 0
    n_samples = 0

    for (rotations, labels) in test_loader:
        rotations = rotations.to(device)
        labels = labels.to(device)
        labels = labels.reshape(labels.shape[0], input_size)
        output = model(rotations)

        test_loss += criterion(output, labels).item()

    loss = test_loss / len(test_loader)
    print(f'loss {loss:.7f}')

predict()