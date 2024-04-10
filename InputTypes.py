from pydantic import BaseModel, constr

class NewPlayer(BaseModel):
    lobby_name: constr(min_length=1, max_length=20)
    team_name: constr(min_length=1, max_length=20)
    player_name: constr(min_length=1, max_length=20)

class Move(BaseModel):
    move: constr(pattern=r'^(UP|DOWN|LEFT|RIGHT)$')

class Start(BaseModel):
    start: constr(pattern=r'^(START)$')
