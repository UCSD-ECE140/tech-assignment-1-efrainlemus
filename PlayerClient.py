import os
import json
from dotenv import load_dotenv

import paho.mqtt.client as paho
from paho import mqtt
import time

game_running = False
next_move = False
moves = {
    "W" : "UP",
    "A" : "LEFT",
    "S" : "DOWN",
    "D" : "RIGHT"
}

# setting callbacks for different events to see if it works, print the message etc.
def on_connect(client, userdata, flags, rc, properties=None):
    """
        Prints the result of the connection with a reasoncode to stdout ( used as callback for connect )
        :param client: the client itself
        :param userdata: userdata is set when initiating the client, here it is userdata=None
        :param flags: these are response flags sent by the broker
        :param rc: stands for reasonCode, which is a code for the connection result
        :param properties: can be used in MQTTv5, but is optional
    """
    print("CONNACK received with code %s." % rc)


# with this callback you can see if your publish was successful
def on_publish(client, userdata, mid, properties=None):
    """
        Prints mid to stdout to reassure a successful publish ( used as callback for publish )
        :param client: the client itself
        :param userdata: userdata is set when initiating the client, here it is userdata=None
        :param mid: variable returned from the corresponding publish() call, to allow outgoing messages to be tracked
        :param properties: can be used in MQTTv5, but is optional
    """
    print("mid: " + str(mid))


# print which topic was subscribed to
def on_subscribe(client, userdata, mid, granted_qos, properties=None):
    """
        Prints a reassurance for successfully subscribing
        :param client: the client itself
        :param userdata: userdata is set when initiating the client, here it is userdata=None
        :param mid: variable returned from the corresponding publish() call, to allow outgoing messages to be tracked
        :param granted_qos: this is the qos that you declare when subscribing, use the same one for publishing
        :param properties: can be used in MQTTv5, but is optional
    """
    print("Subscribed: " + str(mid) + " " + str(granted_qos))


# print message, useful for checking if it was successful
def on_message(client, userdata, msg):
    """
        Prints a mqtt message to stdout ( used as callback for subscribe )
        :param client: the client itself
        :param userdata: userdata is set when initiating the client, here it is userdata=None
        :param msg: the message with topic and payload
    """
    print("message: " + msg.topic + " " + str(msg.qos) + " " + str(msg.payload))
    global game_running
    global next_move
    if 'Error' in msg.payload.decode():
        next_move = True
        game_running = False
    if msg.topic.endswith('/lobby') and msg.payload.decode() == 'Game Over: All coins have been collected':
        game_running = False
    elif msg.topic.endswith('/game_state'):
        next_move = True
    elif msg.topic.endswith('/start') and msg.payload.decode() == 'START':
        game_running = True

def lobby_prompt():
    print("Welcome to the Tech Assignment 1 Game as a Player!")
    option = ""
    while not option.isnumeric() or int(option) not in range(1, 2+1):
        print(
            "Select one of the following options:\n",
            "    1. Create a new lobby\n",
            "    2. Join a lobby"
        )
        option = input("Enter the digit corresponding to the option: ")
    lobby_name = input("Enter the name of the lobby: ")
    player_name = input("Enter your player name: ")
    team_name = input("Enter the name of the team you would like to join: ")
    match int(option):
        case 1:
            return (lobby_name, player_name, team_name, True)
        case 2:
            return (lobby_name, player_name, team_name, False)

def move_prompt():
    print("Enter the letter corresponding to the move you want to make:")
    option = ""
    while option not in moves.keys():
        print(
            "Enter one of the following options to make a move:\n",
            "    W. UP\n",
            "    A. LEFT\n",
            "    S. DOWN\n",
            "    D. RIGHT"
        )
        option = input("Enter your selection: ").upper()
    return option
    

if __name__ == '__main__':
    load_dotenv(dotenv_path='./credentials.env')
    
    broker_address = os.environ.get('BROKER_ADDRESS')
    broker_port = int(os.environ.get('BROKER_PORT'))
    username = os.environ.get('USER_NAME')
    password = os.environ.get('PASSWORD')

    lobby_name, player_name, team_name, creating_lobby = lobby_prompt()

    client = paho.Client(callback_api_version=paho.CallbackAPIVersion.VERSION1, client_id=f"{player_name}", userdata=None, protocol=paho.MQTTv5)

    # enable TLS for secure connection
    client.tls_set(tls_version=mqtt.client.ssl.PROTOCOL_TLS)
    # set username and password
    client.username_pw_set(username, password)
    # connect to HiveMQ Cloud on port 8883 (default for MQTT)
    client.connect(broker_address, broker_port)

    # setting callbacks, use separate functions like above for better visibility
    client.on_subscribe = on_subscribe # Can comment out to not print when subscribing to new topics
    client.on_message = on_message
    client.on_publish = on_publish # Can comment out to not print when publishing to topics

    client.loop_start()

    client.subscribe(f"games/{lobby_name}/lobby", qos=2)
    client.subscribe(f'games/{lobby_name}/{player_name}/game_state', qos=2)
    client.subscribe(f'games/{lobby_name}/scores', qos=2)
    client.subscribe(f'games/{lobby_name}/start', qos=2)

    client.publish("new_game", json.dumps({'lobby_name' : lobby_name,
                                           'team_name' : team_name,
                                           'player_name' : player_name}), qos=2)
    time.sleep(2) # Wait a second to resolve sending game info

    if creating_lobby:
        print("Waiting for other players to join...")
        input("Press enter to start the game: ")
        client.publish(f"games/{lobby_name}/start", "START", qos=2)
    else:
        print("Waiting for game to start...")
        
    while not game_running:
        time.sleep(1) # Wait for game to start

    while True:
        while not next_move:
            time.sleep(2) # Wait to be allowed to make another move
        if not game_running:
            break
        m = move_prompt()
        client.publish(f"games/{lobby_name}/{player_name}/move", moves[m], qos=2)
        next_move = False
        print("Waiting for all players to make a move...")

    if creating_lobby:
        client.publish(f"games/{lobby_name}/start", "STOP", qos=2)

    print("Game has ended!")

    client.loop_stop()

