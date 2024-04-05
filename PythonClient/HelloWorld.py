import grpc
import numpy as np
import asyncio
import player_pb2
import player_pb2_grpc

playerIdentifier = ""
myName = "Kølin"
berserkerBaseName="Bersærker"
warriorNumber = 0

class OccupiedCells:
    Cells = []

    def addCell(self, occupiedCell):
        self.Cells.append(occupiedCell)

    def removeCell(self, address):
        foundCell = self.findCell(address)
        if(foundCell != None):
            self.Cells.remove(foundCell)
    
    def findCell(self, address):
        for cell in self.Cells:
            if self.sameAddress(cell.Address, address):
                return cell
        return None
    
    def sameAddress(self, address1, address2):
        for i in range(len(address1)):
            if address1[i] != address2[i]:
                return False
        return True

class OccupiedCell:
    Address = []
    Player = ""

    def __init__(self, address, player):
        self.Address = address
        self.Player = player

class Snake:
    Head = []
    Segments = [[]]
    Length = 1
    Name = ""
    KidCount = 0

    def __init__(self, address, name):
        print("creating new snake: " + name);
        self.Head = address
        self.Segments.append(address)
        self.Name = name
        print("snake is finished: " + name);

class Cell:
     Address = []
     HasFood = False
     HasPlayer = False

     def __init__(self):
          pass

class GameState:
    Cells = []
    Dimensions = []
    Snakes = []
    OccupiedCells = OccupiedCells()

    def __init__(self, dims, startAddress, playerName):
        self.Snakes.append(Snake(address=startAddress, name=playerName))
        self.Dimensions = dims
        totalCells = np.prod(dims)
        self.Cells = np.array([None]*totalCells).reshape(dims)
    
    def checkBounds(self, lst, indices):
        if indices.any():
            if indices[0] < 0:
                return False
            if len(lst) <= indices[0]:
                return False
            return self.checkBounds(lst[indices[0]], indices[1:])
        return True
    
    def getCell(self, lst, indices, address):
        if indices:
            return self.getCell(lst[indices[0]], indices[1:], address)
        if lst is None:
            lst = Cell()
            lst.Address = address
        return lst
    
    def getCell(self, address):
        cell = self.Cells[tuple(address)]
        if cell is None:
            cell = Cell()
            cell.Address = address
            cell.HasFood = False
            cell.HasPlayer = False
            self.Cells[tuple(address)] = cell
        return cell

    def update(self, gameUpdate, occupiedCells):
        for updatedCell in gameUpdate.updatedCells:
            cell = self.getCell(updatedCell.address)
            cell.HasFood = updatedCell.foodValue > 0
            cell.HasPlayer = len(updatedCell.player) > 0

            # Ignore Bob as that is Mathijs (host)
            if cell.HasPlayer and updatedCell.player != "bob" and updatedCell.player != myName:
                occupiedCells.addCell(OccupiedCell(address=updatedCell.address, player=updatedCell.player))
            else:
                occupiedCells.removeCell(address=updatedCell.address)
                # Length of the snake is the time it spends in the list

    def getNextAddressRandom(self, address):
        while True:
            newaddr = np.copy(address)
            dim = np.random.randint(len(self.Dimensions))
            dir = np.random.randint(2)
            if dir > 0:
                newaddr[dim] += 1
            else:    
                newaddr[dim] -= 1
            if self.checkBounds(self.Cells, newaddr):
                cell = self.getCell(newaddr)
                if cell.HasPlayer == False:
                    return newaddr
    
    def getNextAddressKamikazeMode(self, address):
        sortedCells = sorted(self.OccupiedCells.Cells, key=lambda x: np.linalg.norm(x.Address - address))

        closestPlayer = sortedCells[0]

        # find direction to move to get closer to the closest player
        direction = np.array(closestPlayer.Address) - np.array(address)
        # pick one random direction to move in
        dim = -1
        for i in range(len(direction)):
            if direction[i] != 0:
                dim = i
        # Copy the old address and change the selected direction
        newAddress = np.copy(address)
        if(direction[dim] > 0):
            newAddress[dim] += 1
        else:
            newAddress[dim] -= 1

        return newAddress

    def getMoves(self):
        moves = []
        for snake in self.Snakes:
            if (len(self.OccupiedCells.Cells) > 1):
                nextLocation = self.getNextAddressKamikazeMode(snake.Head)
            else:
                nextLocation = self.getNextAddressRandom(snake.Head)
            snake.Head = nextLocation
            cell = self.getCell(nextLocation)
            snake.Segments.append(nextLocation)
            if cell.HasFood:
                snake.Length += 1
            else:
                snake.Segments = snake.Segments[1:]
            moves.append(player_pb2.Move(playerIdentifier=playerIdentifier, snakeName=snake.Name, nextLocation=nextLocation))
        return moves
    
    def getSplits(self):
        splits = []
        for snake in self.Snakes:
            if snake.Length > 2 and len(self.Snakes) < 11:
                print("old snake:")
                for segment in snake.Segments:
                    print(segment)
                print(" ")
                snake.Length -= 1
                snake.KidCount += 1
                newHead = snake.Segments[0]
                print("new head:")
                print(newHead)
                snake.Segments = snake.Segments[1:]
                print("new head:")
                print(newHead)
                newSnake = Snake(address=newHead, name=snake.Name + "." + str(snake.KidCount)) 
                self.Snakes.append(newSnake)
                address = self.getNextAddress(newHead)
                newSnake.Head = address
                print("new head:")
                print(newSnake.Head)
                cell = self.getCell(address=address)
                newSnake.Segments.append(address)
                if cell.HasFood:
                    newSnake.Length += 1
                else:
                    newSnake.Segments = newSnake.Segments[1:]
                splits.append(player_pb2.SplitRequest(playerIdentifier=playerIdentifier, newSnakeName=newSnake.Name, oldSnakeName=snake.Name, snakeSegment=1, nextLocation=address))
        return splits

async def ListenToServerEvents() -> None:
        with grpc.insecure_channel("192.168.178.62:5168") as channel:
            stub = player_pb2_grpc.PlayerHostStub(channel)
            for thing in stub.SubscribeToServerEvents(player_pb2.EmptyRequest()):
                print(thing)

def Register(playerName):
    with grpc.insecure_channel("192.168.178.62:5168") as channel:
        stub = player_pb2_grpc.PlayerHostStub(channel)
        registerResponse = stub.Register(player_pb2.RegisterRequest(playerName=playerName))
        global playerIdentifier
        gameState = GameState(registerResponse.dimensions, registerResponse.startAddress, playerName)
        playerIdentifier = registerResponse.playerIdentifier
        return gameState

async def Subscribe(gameState) -> None:
        with grpc.insecure_channel("192.168.178.62:5168") as channel:
            stub = player_pb2_grpc.PlayerHostStub(channel)
            for thing in stub.Subscribe(player_pb2.SubsribeRequest(playerIdentifier=playerIdentifier)):
                gameState.update(gameUpdate=thing, occupiedCells=gameState.OccupiedCells)
                for split in gameState.getSplits():
                    stub.SplitSnake(split)
                for move in gameState.getMoves():
                    print(move.snakeName + ": " + str(move.nextLocation))
                    stub.MakeMove(move)

                # loop over snakes and log them
                print("Occupied:")
                for cell in gameState.OccupiedCells.Cells:
                    print(f"{cell.Player} found at {cell.Address}")
                print(" ")

async def main():
    #asyncio.create_task(ListenToServerEvents())
    gameState = Register(myName)
    asyncio.create_task(Subscribe(gameState))

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())