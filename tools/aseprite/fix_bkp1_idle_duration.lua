local FILE = "C:/data/prjs/saboteur-92/assets/sprites/saboteur92_player_bkp1.aseprite"
local spr = app.open(FILE)
spr.frames[1].duration = 100
spr.frames[2].duration = 80
spr.frames[3].duration = 100
spr:saveAs(FILE)
print("idle durations fixed")
