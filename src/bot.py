#!/usr/bin/env python3

import os
from dotenv import load_dotenv
import re
import sys
import time
from daemon import daemon
from pyspades import CARD_SUITS, Player, Team, Game, PLAYER_ACTIONS, BETS
import discord
from discord.ext import commands

def WRAP_RESPONSE(msg):
    return ">>> {}".format(msg)

def STRIP_USER_MENTION(raw):
    match = spadesBot.mentionRegex.fullmatch(raw)
    if match is not None:
        for g in match.groups():
            return int(g)

def SCORE2STRING(d):
    temp = []
    for k in d:
        s = "{}  ({}|{})".format(k, d[k]['score'], d[k]['overbooks'])
        temp.append(s)
    s = "{}    :vs:    {}\n".format(temp[0], temp[1])
    return s

def TURN2STRING(d):
    s = "Turn: {}\tDealer: {}\tSpades Broken? {}\n"
    return s.format(str(d['turn']), str(d['dealer']), str(d['spades_broken']))

def CARDS2STRING(d):
    s = ""
    i = 1
    for c in d['cards']:
        if c.rank.value < 9:
            rank = ":{}:".format(c.rank.name.lower())
        elif c.rank.value == 9:
            rank = ":keycap_ten:"
        else:
            rank = ":regional_indicator_{}:".format(c.rank.name.lower()[0])

        if c.suit == CARD_SUITS.CLUB:
            suit = "<:pyclubs:704357951556550658>"
        elif c.suit == CARD_SUITS.DIAMOND:
            suit = "<:pydiamonds:704357987720101968>"
        elif c.suit == CARD_SUITS.HEART:
            suit = "<:pyhearts:704357987485220875>"
        elif c.suit == CARD_SUITS.SPADE:
            suit = "<:pyspades:704357987925491794>"

        s = "{}({}){} {}\t".format(s, i, rank, suit)
        i = i + 1
    return s

def BET2STRING(d):
    s = "Here's the current booking and betting info:\n"
    for t in d['teams']:
        p1 = t.players[0]
        p2 = t.players[1]
        temp = "__**{} ({}/{}):**__    {} ({}/{})    {} ({}/{})\n"
        temp = temp.format(t.name, t.getNumBooks(), t.getBetNumerical(), p1.name, p1.getNumBooks(), p1.bet.name, p2.name, p2.getNumBooks(), p2.bet.name)
        s = s + temp
    return s

class SpadesBot:
    def __init__(self, bot):
        load_dotenv()
        self.TOKEN = os.getenv('DISCORD_TOKEN')
        self.bot = bot
        self.mentionRegex = re.compile('^<@!(\d+)>$')
        self.reset()

    def run(self):
        self.bot.run(self.TOKEN)

    def reset(self, kwargs=None):
        if kwargs == None:
            self.user_conversion = {}
            self.teams = []
            self.players = []
            self.users = []
        else:
            self.user_conversion = kwargs['converter']
            self.game = None
            self.teams = kwargs['teams']
            self.players = kwargs['players']
            self.users = kwargs['users']

    async def notifyUser(self, user, response):
        if user.dm_channel is None:
            await user.create_dm()
        await user.dm_channel.send(WRAP_RESPONSE(response))       

    async def notifyAll(self, response):
        for u in self.users:
            if u.dm_channel is None:
                await u.create_dm()
            await u.dm_channel.send(WRAP_RESPONSE(response))

class SpadesDaemon(daemon):
    def run(self):
        spadesBot.run()
        while True:
            time.sleep(1)


if __name__ == "__main__":

    bot = commands.Bot(command_prefix='>')
    spadesBot = SpadesBot(bot)

    helpString = "Assemble a fantastic team."
    @bot.command(name="team", help=helpString)
    async def start_new_team(ctx, teamName, user1, user2):
        if len(spadesBot.teams) >= 2:
            spadesBot.reset()

        user1 = STRIP_USER_MENTION(user1)
        user2 = STRIP_USER_MENTION(user2)

        user1 = discord.utils.find(lambda m: m.id == user1, ctx.channel.guild.members)
        user2 = discord.utils.find(lambda m: m.id == user2, ctx.channel.guild.members)
        spadesBot.users.extend([user1, user2])

        player1 = Player(user1.id, user1.name)
        player2 = Player(user2.id, user2.name)
        spadesBot.players.extend([player1, player2])

        spadesBot.user_conversion.update({
            str(user1.id): player1,
            str(user2.id): player2
        })

        t = Team(teamName, [player1, player2])
        spadesBot.teams.append(t)

        response = "Team {} joined the game!".format(teamName)
        if len(spadesBot.teams) == 1:
            response = response + " You need one more team to start a game."
        elif len(spadesBot.teams) == 2:
            response = response + " Both teams are here, start a game with -game <maxScore>."
        await spadesBot.notifyAll(response)

    helpString = "Start a new game. Two teams must be created before this command."
    @bot.command(name="game", help=helpString)
    async def start_new_game(ctx, maxScore: int):
        numTeams = len(spadesBot.teams)
        if numTeams <= 1:
            response = "Need to make 2 teams, there's only {}.".format(numTeams)
        elif numTeams > 2:
            response = "There are too many teams. Get rid of them by making new teams with \"!new t <team name> <user1 name> <user2 name>\"."
        elif numTeams == 2:
            spadesBot.game = Game(spadesBot.teams, maxScore)
            response = spadesBot.game.notification
        await spadesBot.notifyAll(response)

    helpString = "Deal cards."
    @bot.command(name="deal", help=helpString)
    async def deal(ctx):
        userid = ctx.author.id
        player = spadesBot.user_conversion[str(userid)]

        if spadesBot.game == None:
            await ctx.send(WRAP_RESPONSE("A game hasn't been created yet. Make one with \'>game [score]\'"))
        else:
            # Debug only
            if len(spadesBot.user_conversion) < 4:
                for p in spadesBot.players:
                    if p.id == player.id:
                        if spadesBot.game.playerAction(p, PLAYER_ACTIONS.DEAL, 0):
                            break
            else:
                spadesBot.game.playerAction(player, PLAYER_ACTIONS.DEAL, 0)

            response = spadesBot.game.notification
            await spadesBot.notifyAll(response)

    helpString = "Make a bet where <betInput> can be any number, \'n\' for nil, or \'tth\' for ten-two-hundred."
    @bot.command(name="bet", help=helpString)
    async def bet(ctx, betInput):
        userid = ctx.author.id
        player = spadesBot.user_conversion[str(userid)]

        bet = BETS.NONE
        try:
            betInput = int(betInput)
            if betInput <= 13:
                bet = BETS(betInput)
        except ValueError:
            if betInput == 'n':
                bet = BETS.NIL
            elif betInput == "tth":
                bet = BETS.TTH

        # Debug only
        if len(spadesBot.user_conversion) < 4:
            for p in spadesBot.players:
                if p.id == player.id:
                    if spadesBot.game.playerAction(p, PLAYER_ACTIONS.BET, bet):
                        break
        else:
            spadesBot.game.playerAction(player, PLAYER_ACTIONS.BET, bet)

        response = spadesBot.game.notification
        await spadesBot.notifyAll(response)

    helpString = "Play a card where <cardIndex> is the order the card is in your hand."
    @bot.command(name="play", help=helpString)
    async def play(ctx, cardIndex: int):
        userid = ctx.author.id
        player = spadesBot.user_conversion[str(userid)]

        # Debug only
        if len(spadesBot.user_conversion) < 4:
            for p in spadesBot.players:
                if p.id == player.id:
                    if spadesBot.game.playerAction(p, PLAYER_ACTIONS.PLAY, cardIndex):
                        break
        else:
            spadesBot.game.playerAction(player, PLAYER_ACTIONS.PLAY, cardIndex)

        response = spadesBot.game.notification
        await spadesBot.notifyAll(response)

    helpString = "Ask to see your hand."
    @bot.command(name="hand", help=helpString)
    async def show_hand(ctx):
        userid = ctx.author.id
        player = spadesBot.user_conversion[str(userid)]

        if ctx.author.dm_channel is None:
            await ctx.author.create_dm()

        # Debug only
        if len(spadesBot.user_conversion) < 4:
            player = spadesBot.game.getPlayerByTurnOrder(spadesBot.game.whoseTurn)
            
        response = "Here's your hand, sport:\n"
        response = response + CARDS2STRING({"cards": player.hand})
        await ctx.author.dm_channel.send(WRAP_RESPONSE(response))

    helpString = "Ask to see the betting info and current books."
    @bot.command(name="books", help=helpString)
    async def show_betting_info(ctx):
        userid = ctx.author.id
        player = spadesBot.user_conversion[str(userid)]

        d = spadesBot.game.getBettingInfo(dict)
        await spadesBot.notifyUser(ctx.author, BET2STRING(d))

    helpString = "Ask to see the current game's info."
    @bot.command(name="show", help=helpString)
    async def show_game(ctx):
        userid = ctx.author.id

        d = spadesBot.game.getScoreInfo(dict)
        response = SCORE2STRING(d)

        d = spadesBot.game.getTurnInfo(dict)
        response = response + TURN2STRING(d)

        d = spadesBot.game.getPileInfo(dict)
        response = response + CARDS2STRING(d)

        await spadesBot.notifyUser(ctx.author, response)

    helpString = "Have a rematch with the same teams. The dealer gets rotated."
    @bot.command(name="rematch", help=helpString)
    async def rematch(ctx, teamName, user1, user2):
        uc = spadesBot.user_conversion
        teams = spadesBot.teams
        players = spadesBot.players
        maxScore = spadesBot.game.maxScore

        spadesBot.reset({"converter": uc, "teams": teams, "players": players, "users": []})

        spadesBot.game = Game(spadesBot.teams, maxScore)
        response = spadesBot.game.notification
        await spadesBot.notifyAll(response)

    daemon = SpadesDaemon('/tmp/spadesbot-daemon.pid')
    if len(sys.argv) == 2:
        if 'start' == sys.argv[1]:
            daemon.start()
        elif 'stop' == sys.argv[1]:
            daemon.stop()
        elif 'restart' == sys.argv[1]:
            daemon.restart()
        else:
            print("Unknown command")
            sys.exit(2)
        sys.exit(0)
    else:
        print("usage: %s start|stop|restart" % sys.argv[0])
        sys.exit(2)