from discord.ext import commands
from bigtwo import BigTwo
from server import Server
import random as rnd
import time

# Global functions
def get_token():
    with open(".token", "r") as f:
        return f.read()


def context_unpack(ctx):
    s = ctx.message.guild.id
    c = ctx.message.channel.id
    n = ctx.message.author.id
    l = "{}-{}".format(s, c)
    return [s, c, n, l]


# Game functions
async def direct_message_card(ctx, player_pool):
    for p in player_pool:
        player = player_pool[p]
        emoji_list = [
            f"{next(filter(lambda emoji: emoji_name == emoji.name , bot.emojis))}"
            for emoji_name in player.get_card_discord_format()
        ]
        await player.player_object.send("".join(emoji_list))


async def direct_message_stop(ctx, player_pool):
    for p in player_pool:
        player = player_pool[p]
        await player.player_object.send("Game stopped.")


async def direct_message_winner(ctx, player_pool, winner_id):
    for p in player_pool:
        player = player_pool[p]
        if p == winner_id:
            await player.player_object.send("You are the winner!")
            return
        await player.player_object.send("Game ended.")


async def show_board(ctx, lobby):
    owner = lobby.current_owner
    combo = lobby.current_combo
    card_list_msg = "\n".join([n.emoji() for n in combo.card_list])
    card_left = len(lobby.player_pool[owner].cards)
    description = "`{} by` <@{}> `{} card{} left`".format(
        combo._type.capitalize(), owner, card_left, "s" * int(card_left > 1)
    )
    await ctx.send("{}\n{}".format(card_list_msg, description))


async def show_turn(ctx, lobby):
    player = lobby.whos_turn()
    owner = lobby.current_owner
    combo = lobby.current_combo
    msg = "It's your turn. <@{}>".format(player)
    if combo == None:
        msg += "\nIt's free to throw."
    await ctx.send(msg)


# Constants
TOKEN = get_token()
RETRY_DELAY = 60
MAX_NUMBER = 26

# Server object for lobbies
SERVER = Server("BigTwo")

# Instantiate bot and set command prefix
bot = commands.Bot(command_prefix="-")

# Events
@bot.event
async def on_ready():
    print("BigTwo bot is up...")


# Remove build-in command
bot.remove_command("help")

# Commands - General
@bot.command(pass_context=True)
async def ping(ctx):
    await ctx.send("Pong!")


@bot.command(pass_context=True)
async def random(ctx, mode="card", number=1):
    if number > MAX_NUMBER:
        await ctx.send("Limit number is {}".format(MAX_NUMBER))
        return
    s = ""
    if mode == "card":
        s = [
            "`{:0>2d}` {}".format(n + 1, BigTwo.DECK.get_random().emoji())
            for n in range(number)
        ]
    if mode == "suit":
        s = [
            "`{:0>2d}` {}".format(n + 1, BigTwo.SUITSET.get_random()._emoji)
            for n in range(number)
        ]
    if mode == "rank":
        s = [
            "`{:0>2d}` {}".format(n + 1, BigTwo.RANKSET.get_random()._emoji)
            for n in range(number)
        ]
    await ctx.send("\n".join(s))


@bot.command(pass_context=True)
async def flip(ctx, number=1):
    if number > MAX_NUMBER:
        await ctx.send("Limit number is {}".format(MAX_NUMBER))
        return
    r = ["`Head`", "`Tail`"]
    s = ["`{:0>2d}` `{}`".format(n + 1, r[rnd.randint(0, 1)]) for n in range(number)]
    await ctx.send("\n".join(s))


# Commands - Lobby
@bot.command(pass_context=True)
async def create(ctx):
    s, c, n, l = context_unpack(ctx)
    for lobby in SERVER.lobby_list:
        if n in SERVER.lobby_list[lobby].player_pool:
            await ctx.send(
                "You already joined a game in other channel. <@{}>".format(n)
            )
            return
    if SERVER.add_lobby(s, c):
        await ctx.send("<@{}> created a game in this channel.".format(n))
        SERVER.lobby_list[l].join(ctx.message.author)
        SERVER.lobby_list[l].set_host(n)
        return
    await ctx.send("This channel is occupied. <@{}>".format(n))


@bot.command(pass_context=True)
async def join(ctx):
    s, c, n, l = context_unpack(ctx)
    if l in SERVER.lobby_list:
        if SERVER.lobby_list[l].started:
            return
        if n in SERVER.lobby_list[l].player_pool:
            await ctx.send("Already joined this game. <@{}>".format(n))
            return
        if len(SERVER.lobby_list[l].player_pool) == 4:
            await ctx.send("This game is full. <@{}>".format(n))
            return
        for lobby in SERVER.lobby_list:
            if n in SERVER.lobby_list[lobby].player_pool:
                await ctx.send(
                    "You already joined a game in other channel. <@{}>".format(n)
                )
                return
        if SERVER.lobby_list[l].join(ctx.message.author):
            await ctx.send("Joined game! <@{}>".format(n))
            return
        await ctx.send("Sorry, this game is full. <@{}>".format(n))


@bot.command(pass_context=True)
async def leave(ctx):
    s, c, n, l = context_unpack(ctx)
    if l in SERVER.lobby_list:
        if n not in SERVER.lobby_list[l].player_pool:
            await ctx.send("You did not join any game. <@{}>".format(n))
            return
        if SERVER.lobby_list[l].started:
            await ctx.send("Abandoned game! <@{}>".format(n))
        else:
            await ctx.send("Game left! <@{}>".format(n))
        if SERVER.lobby_list[l].leave(ctx.message.author):
            SERVER.remove_lobby(s, c)
            await ctx.send("Everyone has left the game, game closed.")
            return
        if len(SERVER.lobby_list[l].player_pool) == 1 & SERVER.lobby_list[l].started:
            SERVER.lobby_list[l].stop()
            await ctx.send("Only 1 player left, game stopped.")
            await direct_message_stop(ctx, SERVER.lobby_list[l].player_pool)
        if SERVER.lobby_list[l].host_id == n:
            new_host = SERVER.lobby_list[l].set_random_host()
            await ctx.send("Host left, <@{}> is assigned as new host.".format(new_host))
            return


@bot.command(pass_context=True)
async def start(ctx):
    s, c, n, l = context_unpack(ctx)
    if l in SERVER.lobby_list:
        if n != SERVER.lobby_list[l].host_id:
            await ctx.send("You are not the host. <@{}>".format(n))
            return
        if SERVER.lobby_list[l].started:
            await ctx.send("Game already started. <@{}>".format(n))
            return
        if len(SERVER.lobby_list[l].player_pool) < 2:
            await ctx.send('This game need at least 2 players. <@{}>'.format(n))
            return
        SERVER.lobby_list[l].start()
        await ctx.send("Game started! Your cards will be direct messaged to you.")
        await show_turn(ctx, SERVER.lobby_list[l])
        await direct_message_card(ctx, SERVER.lobby_list[l].player_pool)


@bot.command(pass_context=True)
async def stop(ctx):
    s, c, n, l = context_unpack(ctx)
    if l in SERVER.lobby_list:
        if n != SERVER.lobby_list[l].host_id:
            await ctx.send("You are not the host. <@{}>".format(n))
            return
        if not SERVER.lobby_list[l].stop():
            await ctx.send("Game already stopped. <@{}>".format(n))
            return
        await ctx.send("Game stopped by host.")


@bot.command(pass_context=True)
async def throw(ctx, *args):
    s, c, n, l = context_unpack(ctx)
    if l in SERVER.lobby_list:
        if n not in SERVER.lobby_list[l].player_pool:
            return
        if not SERVER.lobby_list[l].started:
            return
        indexes = []
        try:
            indexes = [int(n) for n in args]
        except Exception:
            await ctx.send("Invalid input. <@{}>".format(n))
            return
        player = SERVER.lobby_list[l].player_pool[n]
        player_cards = player.cards
        if max(indexes) >= len(player_cards):
            await ctx.send("Index exceed card number. <@{}>".format(n))
            return
        cards = player.peek_cards(indexes)
        res = SERVER.lobby_list[l].attack(n, cards)
        res_msg = [
            "Not your turn. <@{}>".format(n),
            "Invalid card combination. <@{}>".format(n),
            "Opponent card is better. <@{}>".format(n),
        ]
        if res != 0:
            await ctx.send(res_msg[res - 1])
            return
        player.throw_cards(indexes)
        await show_board(ctx.message.channel, SERVER.lobby_list[l])
        # Check victory
        if len(player.cards) == 0:
            SERVER.lobby_list[l].stop()
            await ctx.send("<@{}> wins the game!".format(n))
            await direct_message_winner(ctx, SERVER.lobby_list[l].player_pool, n)
            return
        await show_turn(ctx, SERVER.lobby_list[l])
        await direct_message_card(ctx, {n: SERVER.lobby_list[l].player_pool[n]})


@bot.command(pass_context=True)
async def skip(ctx, *args):
    s, c, n, l = context_unpack(ctx)
    if l in SERVER.lobby_list:
        if n not in SERVER.lobby_list[l].player_pool:
            return
        if not SERVER.lobby_list[l].whos_turn() == n:
            return
        if SERVER.lobby_list[l].current_combo == None:
            await ctx.send("You cannot skip a free throw round. <@{}>".format(n))
            return
        SERVER.lobby_list[l].next_turn()
        await ctx.send("<@{}> skipped.".format(n))
        await show_turn(ctx, SERVER.lobby_list[l])


while True:
    try:
        bot.loop.run_until_complete(bot.start(TOKEN))
    except BaseException:
        print("Connection error, retry in " + str(RETRY_DELAY) + " seconds.")
        time.sleep(RETRY_DELAY)
