import discord
import asyncio
import random
import time
import aiosqlite

from cardcast import api

import config
import info
import tokens
import yaml

class Shard:
    def __init__(self, shard, client, num_shards=4):       
        self.shard = shard
        self.client = client
        self.num_shards = num_shards
    
    async def deal(self, ch):
        """Deals cards to each player within a given channel."""
        
        for i in range(config.C[ch]['nPlayers']):
            await self.dealOne(ch, i)
        config.C[ch]['time'] = time.time()
    
    async def dealOne(self, ch, i):
        """Deal cards to one player in a given channel."""
        
        config.C[ch]['played'][i] = False
        
        # don't deal cards to czar
        #if i == config.C[ch]['pov']:
        #    return
        
        nCards = 10 if config.nCards(ch) < 3 else 12
        while len(config.C[ch]['hands'][i]) < nCards:
            config.C[ch]['hands'][i].append(config.C[ch]['white'][0])
            config.C[ch]['white'] = config.C[ch]['white'][1:]
        await self.sendHand(ch,i)
    
    async def start_(self, ch):
        """Begin a game."""
        
        config.C[ch]['started'] = True
        
        for _ in range(config.C[ch]['nPlayers']):
            config.C[ch]['hands'].append([])
            config.C[ch]['played'].append(False)
            config.C[ch]['score'].append(0)
            config.C[ch]['kick'].append('')
        
        # add blanks
        for _ in range(config.C[ch]['blanks']):
            config.C[ch]['white'].append('')
        
        await config.shuffle(ch)
        config.C[ch]['curr'] = await config.nextBlack(ch)
        await self.deal(ch)
        
        config.C[ch]['pov'] = 0
    
    async def pass_(self, ch):
        """Move on to the next round."""
        
        config.C[ch]['pov'] = (config.C[ch]['pov']+1) % config.C[ch]['nPlayers'] # next czar
        config.C[ch]['curr'] = await config.nextBlack(ch)
        config.C[ch]['mid'] = []
        config.C[ch]['msg'] = None
        
        await self.deal(ch)
        await self.displayMid(ch)
    
    async def addPack(self, ch, s):
        """Given a pack name, try to add that pack."""
        
        s = s.strip()
        
        success = total = added = 0
        
        # CardCast
        try:
            if s not in config.C[ch]['packs']:
                b, w = api.get_deck_blacks_json(s), api.get_deck_whites_json(s)
                config.C[ch]['black'] += ['_'.join(c['text']) for c in b]
                config.C[ch]['white'] += [''.join(c['text']) for c in w]
                
                config.C[ch]['packs'].append(s)
                
                success += 1
                total += 1
            else:
                added += 1
                total += 1
        except:
            pass
        
        s = s.lower()
        
        # add all official packs
        if s == 'all':
            await self.addPack(ch, ''.join(x for x in config.packs))
            return
        
        # add all third party packs
        if s == '3rdparty' or s == 'thirdparty':
            await self.addPack(ch, ''.join(x for x in config.thirdparty))
            return
        
        # add the red, green, and blue expansions
        if s == 'rgb':
            await self.addPack(ch, 'redbluegreen')
            return
        
        for p in config.packs:
            if p == 'cats' and s.count('cats') == s.count('cats2'):
                continue
            
            if p in s:
                total += 1
                if p not in config.C[ch]['packs']:
                    config.C[ch]['black'] += list(eval('config.black_'+p))
                    config.C[ch]['white'] += list(eval('config.white_'+p))
                    
                    config.C[ch]['packs'].append(p)
                    
                    success += 1
                else:
                    added += 1
        for p in config.thirdparty:
            if p in s:
                total += 1
                if p not in config.C[ch]['packs']:
                    config.C[ch]['black'] += list(eval('config.black_'+p))
                    config.C[ch]['white'] += list(eval('config.white_'+p))
                    
                    config.C[ch]['packs'].append(p)
                    
                    success += 1
                else:
                    added += 1
        
        if total:
            msg = 'Successfully added ' + str(success) + ' out of ' + str(total) + (' packs' if total > 1 else ' pack')
            if added: msg += '\n' + str(added) + (' packs' if added > 1 else ' pack') + ' already added'
            await self.client.send_message(ch, msg)
            await self.edit_start_msg(ch)
    
    async def removePack(self, ch, s):
        """Given a pack name, try to remove that pack."""
        
        s = s.strip()
        
        # CardCast
        try:
            if s in config.C[ch]['packs']:
                b, w = api.get_deck_blacks_json(s), api.get_deck_whites_json(s)
                config.C[ch]['black'] = [x for x in config.C[ch]['black'] if x not in ['_'.join(c['text']) for c in b]]
                config.C[ch]['white'] = [x for x in config.C[ch]['white'] if x not in [''.join(c['text']) for c in w]]
                
                config.C[ch]['packs'].remove(s)
                await self.client.send_message(ch, s + ' removed!')
        except:
            pass
        
        s = s.lower()
        
        for p in config.packs:
            if p in s and p in config.C[ch]['packs']:
                config.C[ch]['black'] = [x for x in config.C[ch]['black'] if x not in eval('config.black_'+p)]
                config.C[ch]['white'] = [x for x in config.C[ch]['white'] if x not in eval('config.white_'+p)]
                
                config.C[ch]['packs'].remove(p)
                await self.client.send_message(ch, config.packs[p] + ' removed!')
        for p in config.thirdparty:
            if p in s and p in config.C[ch]['packs']:
                config.C[ch]['black'] = [x for x in config.C[ch]['black'] if x not in eval('config.black_'+p)]
                config.C[ch]['white'] = [x for x in config.C[ch]['white'] if x not in eval('config.white_'+p)]
                
                config.C[ch]['packs'].remove(p)
                await self.client.send_message(ch, config.thirdparty[p] + ' removed!')
        
        # remove red, green, and blue expansions
        if s == 'rgb':
            await self.removePack(ch, 'redgreenblue')
        
        # remove base pack
        if 'base' in s and 'base' in config.C[ch]['packs']:
            config.C[ch]['black'] = [x for x in config.C[ch]['black'] if x not in config.black]
            config.C[ch]['white'] = [x for x in config.C[ch]['white'] if x not in config.white]
            config.C[ch]['packs'].remove('base')
            await self.client.send_message(ch, 'Base Cards Against Humanity removed!')
        
        # remove all packs
        if len(config.C[ch]['black']) * len(config.C[ch]['white']) == 0 or s == 'all':
            if config.C[ch]['lang'] == 'English':
                config.C[ch]['black'] = list(config.black)
                config.C[ch]['white'] = list(config.white)
            else:
                config.C[ch]['black'] = list(eval('config.black_'+config.languages[config.C[ch]['lang']]))
                config.C[ch]['white'] = list(eval('config.white_'+config.languages[config.C[ch]['lang']]))
            
            config.C[ch]['packs'] = ['base']
            await self.client.send_message(ch, 'No cards left. Reverting to base pack')
        
        await self.edit_start_msg(ch)
    
    async def play(self, ch, p, s):
        s = s.strip().replace(' ','').replace(',','').replace('<','').replace('>','')
        
        player = None
        # check that player is in current game
        try:
            player = config.C[ch]['players'].index(p)
        except:
            return
        
        if config.C[ch]['played'][player] or player == config.C[ch]['pov']:
            return
        
        try:
            newMid = []
            for x in s:
                card = config.C[ch]['hands'][player]['abcdefghijkl'.index(x)]
                if card in newMid:
                    return
                # check for blank
                if card == '':
                    await self.client.send_message(p,
                        "You tried to send a blank card without filling it in first!\nMessage me what you'd like to put in the blank.")
                    return
                newMid.append(card)
    
            if len(newMid) == config.nCards(ch):
                config.C[ch]['mid'].append([newMid,player])
                for c in newMid:
                    config.C[ch]['white'].append(c)
                    config.C[ch]['hands'][player].remove(c)
                config.C[ch]['played'][player] = True
                await self.client.send_message(ch, p.display_name + ' has played!')
            else:
                await self.client.send_message(p, 'This prompt requires ' + str(config.nCards(ch)) + ' white card(s).')
                return
            
            # update kicks
            for k in range(len(config.C[ch]['kick'])):
                if config.C[ch]['kick'][k] == p.mention:
                    config.C[ch]['kick'][k] = ''
            
            # all players are done
            if config.done(ch):
                mid = []
                while len(config.C[ch]['mid']) != 0:
                    rm = random.randint(0,len(config.C[ch]['mid'])-1)
                    mid.append(config.C[ch]['mid'][rm])
                    config.C[ch]['mid'] = config.C[ch]['mid'][:rm] + config.C[ch]['mid'][rm+1:]
                config.C[ch]['mid'] = mid
                
                config.C[ch]['time'] = time.time()
            
            await self.displayMid(ch)
        except:
            pass
    
    async def sendHand(self, ch, i):
        t = 'Your white cards in #' + ch.name + ' (' + ch.server.name + '):'
        msg = ''
        hasBlank = False
        for card in range(len(config.C[ch]['hands'][i])):
            s = config.C[ch]['hands'][i][card]
            if s == '':
                s = "<blank card>"
                hasBlank = True
            msg += '**' + 'ABCDEFGHIJKL'[card] + ')** ' + s + '\n'
        
        if config.C[ch]['pov'] == i:
            msg += '\n**You are the Czar this round; you do NOT need to play any cards.**'
        msg += '\nBlack card:\n' + config.C[ch]['curr']
        msg = msg.replace('_', '\_'*5)
        
        em = discord.Embed(title=t, description=msg, colour=0xBBBBBB)
        
        if hasBlank:
            if config.C[ch]['players'][i] not in config.P:
                config.P[config.C[ch]['players'][i]] = [ch]
            elif ch not in config.P[config.C[ch]['players'][i]]:
                config.P[config.C[ch]['players'][i]].append(ch)
            em.set_footer(text='It looks like you have one or more blank cards.\nTo fill in the blank, simply message me your answer.')
        
        try:
            await self.client.send_message(config.C[ch]['players'][i], embed=em)
        except:
            try:
                await self.client.send_message(ch, 'Unable to send hand to ' + config.C[ch]['players'][i].mention + ', do they have private messaging enabled?')
            except:
                print('Error getting player ' + str(i) + ' out of ' + str(config.C[ch]['nPlayers']))
    
    async def displayMid(self, ch):
        # don't display if not enough players
        if config.C[ch]['nPlayers'] < 2: return
        
        msg = '─'*20 + '\n'
        for i in range(config.C[ch]['nPlayers']):
            msg += config.C[ch]['players'][i].display_name + ' - ' + str(config.C[ch]['score'][i])
            if config.C[ch]['played'][i] and not config.done(ch): msg += ' **Played!**'
            elif config.C[ch]['pov'] == i: msg += ' **Czar**'
            msg += '\n'
        
        if config.C[ch]['win'] not in config.C[ch]['score']:
            msg += '\nCurrent Czar: ' + config.C[ch]['players'][config.C[ch]['pov']].mention + '\n\n'
            msg += 'Black card:\n' + config.C[ch]['curr'].replace('_','\_'*5) + '\n'
        
        if config.done(ch):
            msg += '\n'
            for m in range(len(config.C[ch]['mid'])):
                msg += '**' + 'ABCDEFGHIJKL'[m] + ')** '
                for card in config.C[ch]['mid'][m][0]:
                    msg += card + '\n'
        
        msg += '─'*20
        
        try:
            #em = discord.Embed(description=msg, colour=0xBBBBBB)
            if config.C[ch]['msg'] == None or config.done(ch):
                #config.C[ch]['msg'] = await self.client.send_message(ch, embed=em)
                config.C[ch]['msg'] = await self.client.send_message(ch, msg)
                config.C[ch]['time'] = time.time()
            else:
                #await self.client.edit_message(config.C[ch]['msg'], embed=em)
                await self.client.edit_message(config.C[ch]['msg'], msg)
        except:
            print('Error in displayMid() at\n' + time.asctime() + '\n')
            c = config.pre[ch.id] if ch.id in config.pre else 'c'
            await self.client.send_message(ch,
                'Encountered error while displaying - answer selection may not function normally. If the czar is unable to select, try using `'+c+'!display`.')
            return
        
        if config.done(ch):
            letters = ['\U0001F1E6','\U0001F1E7','\U0001F1E8','\U0001F1E9','\U0001F1EA',
                       '\U0001F1EB','\U0001F1EC','\U0001F1ED','\U0001F1EE','\U0001F1EF']
            error_occured = False
            for i in range(config.C[ch]['nPlayers']-1):
                try:
                    await self.client.add_reaction(config.C[ch]['msg'], letters[i])
                except:
                    if not error_occured:
                        error_occured = True
                        await self.client.send_message(ch,
                            'An error occurred while adding a letter; if the letter of your choice is not shown, please choose it by adding the letter manually.')
    
    async def displayWinners(self, ch):
        winner = config.C[ch]['score'].index(max(config.C[ch]['score']))
        msg = '\U0001F947' + ' ' + config.C[ch]['players'][winner].display_name + '\n'
        c = config.pre[ch.id] if ch.id in config.pre else 'c'
        msg += 'Use `'+c+'!start` to start another game!'
        await self.client.send_message(ch, msg)
    
    async def addPlayer(self, ch, p):
        if config.C[ch]['nPlayers'] < 10:
            config.C[ch]['players'].append(p)
            config.C[ch]['nPlayers'] = len(config.C[ch]['players'])
            config.C[ch]['played'].append(False)
            config.C[ch]['score'].append(0)
            config.C[ch]['hands'].append([])
            config.C[ch]['kick'].append('')
            
            await self.client.send_message(ch, p.display_name + ' has joined the game.')
            await self.dealOne(ch,config.C[ch]['nPlayers']-1)
            await self.displayMid(ch)
        else:
            await self.client.send_message(ch, 'Game is at max capacity!')
    
    async def removePlayer(self, ch, p, kick=False):
        if p in config.C[ch]['players']:
            i = config.C[ch]['players'].index(p)
            
            if config.C[ch]['played'][i]:
                await self.client.send_message(ch, 'You have already played your cards and may not leave.')
                return
            
            config.C[ch]['players'] = config.C[ch]['players'][:i]+config.C[ch]['players'][i+1:]
            config.C[ch]['played'] = config.C[ch]['played'][:i]+config.C[ch]['played'][i+1:]
            config.C[ch]['hands'] = config.C[ch]['hands'][:i]+config.C[ch]['hands'][i+1:]
            config.C[ch]['score'] = config.C[ch]['score'][:i]+config.C[ch]['score'][i+1:]
            config.C[ch]['kick'] = config.C[ch]['kick'][:i]+config.C[ch]['kick'][i+1:]
            
            if i < config.C[ch]['pov']:
                config.C[ch]['pov'] -= 1
            
            config.C[ch]['nPlayers'] = len(config.C[ch]['players'])
            config.C[ch]['pov'] %= config.C[ch]['nPlayers']
            
            # update cards already in the middle
            for j in range(len(config.C[ch]['mid'])):
                if config.C[ch]['mid'][j][1] > i:
                    config.C[ch]['mid'][j][1] -= 1
            
            # all players are done
            if config.done(ch):
                mid = []
                while len(config.C[ch]['mid']) != 0:
                    rm = random.randint(0,len(config.C[ch]['mid'])-1)
                    mid.append(config.C[ch]['mid'][rm])
                    config.C[ch]['mid'] = config.C[ch]['mid'][:rm] + config.C[ch]['mid'][rm+1:]
                config.C[ch]['mid'] = mid
            
            if not kick:
                await self.client.send_message(ch, p.display_name + ' has left the game.')
            await self.displayMid(ch)
        if config.C[ch]['nPlayers'] < 2:
            await config.reset(ch)
            await self.client.send_message(ch, 'Not enough players, game has been reset.')
    
    async def get_start_msg(self, ch):
        c = config.pre[ch.id] if ch.id in config.pre else 'c'
        
        s = ("Use `{0}!join` to join (and `{0}!leave` if you have to go)!\n"
            "Use `{0}!add <pack>` to add an expansion pack (`{0}!packs` to show all available packs).\n"
            "Current packs: "+', '.join(p for p in config.C[ch]['packs'])+'\n'
            "Use `{0}!setwin <#>` to change the number of points to win (current: "+str(config.C[ch]['win'])+')\n'
            "Use `{0}!timer <# sec>` to change the duration of the idle timer (current: "+str(config.C[ch]['timer'])+"), or use `c!timer 0` to disable it.\n"
            "Use `{0}!setblank <#>` to change the number of blank cards (max 30, current: "+str(config.C[ch]['blanks'])+')\n'
            "Use `{0}!language <lang>` to change the language (current: "+str(config.C[ch]['lang'])+')\n'
            "Once everyone has joined, type `{0}!start` again to begin.").format(c)
        
        return s
    
    async def edit_start_msg(self, ch):
        if not config.C[ch]['playerMenu']: return
        
        s = await self.get_start_msg(ch)
        await self.client.edit_message(config.C[ch]['msg'], s)
    
    async def on_ready(self):
        await self.client.change_presence(game=discord.Game(name='c!help'))
        
        # SQL setup
        if self.shard != 0:
            async with aiosqlite.connect('messages{0}.db'.format(self.shard)) as conn:
                C = await conn.cursor()
                try:
                    await C.execute("""create table if not exists Messages(id text, msg text);""")
                    await conn.commit()
                except:
                    pass
        
        print('Ready shard {0}'.format(self.shard))

    async def on_message(self, message):
        #if (time.time() / 3600) - last_update > 1:
        #    await self.client.change_presence(game=discord.Game(name='on '+'_'*4+' servers. ' + str(len(client.servers))+'.'))
        #    config.last_update = time.time() / 3600
        
        msg = message.content.lower()
        ch = message.channel
        au = message.author
        
        # ignore own messages
        if au.id == '429024440060215296':
            return
        
        c = config.pre[ch.id] if ch.id in config.pre else 'c'
        
        # fill in blank cards
        if self.shard == 0:
            if ch.is_private and au.id != '429024440060215296':
                # check for c!p or c!play
                if (len(msg) > 3 and msg[:3] == c+'!p') or (len(msg) > 6 and msg[:6] == c+'!play'):
                    await self.client.send_message(au, 'Please play your card(s) in the corresponding channel and not as a private message.')
                    return
                
                found = False
                if au in config.P: # check that user has a blank card
                    for c in config.P[au]: # check all channels that user is in
                        if config.C[c]['started'] and au in config.C[c]['players']: # check that user is currently playing
                            i = config.C[c]['players'].index(au)
                            if '' in config.C[c]['hands'][i]: # check that player has a blank
                                found = True
                                j = config.C[c]['hands'][i].index('')
                                config.C[c]['hands'][i][j] = message.content.replace('*','\*').replace('_','\_').replace('~','\~').replace('`','\`')
                                await self.sendHand(c, i)
                                break
                if not found:
                    edited_msg = message.content.replace('*','\*').replace('_','\_').replace('~','\~').replace('`','\`')
                    for i in range(1, self.num_shards):
                        async with aiosqlite.connect('messages{0}.db'.format(i)) as conn:
                            C = await conn.cursor()
                            await C.execute("""insert into Messages values (?, ?)""", (au.id, edited_msg))
                            await conn.commit()
                
                return
        
        if ch not in config.C:
            config.C[ch] = {}
            await config.initChannel(ch)
        
        # warning
        if len(msg) > 9 and msg[:9] == c+'!warning' and au.id == '252249185112293376':
            for x in config.C:
                if config.C[x]['started']:
                    await self.client.send_message(x, message.content[9:])
        # check number of ongoing games
        if msg == c+'!ongoing' and au.id == '252249185112293376':
            nC = 0
            for x in config.C:
                if config.C[x]['started']:
                    nC += 1
            await self.client.send_message(ch, str(nC))
        
        # changelog
        if msg == c+'!whatsnew' or msg == c+'!update' or msg == c+'!updates':
            s = info.changelog
            await self.client.send_message(ch, s[:s.index('**9/11')])
        
        # commands list
        if msg == c+'!commands' or msg == c+'!command':
            await self.client.send_message(ch, info.commands)
            #await self.client.send_message(ch, "You can find a list of available commands here:\nhttps://discordbots.org/bot/429024440060215296")
        
        # support server
        if msg == c+'!support' or msg == c+'!server' or msg == c+'!supp':
            await self.client.send_message(ch, 'https://discord.gg/qGjRSYQ')
        
        # invite link
        if msg == c+'!invite':
            await self.client.send_message(ch,
                'Use this link to invite the bot to your own server:\n<https://discordapp.com/api/oauth2/authorize?client_id=429024440060215296&permissions=134294592&scope=bot>')
        
        # vote link
        if msg == c+'!vote':
            await self.client.send_message(ch,
                'Use this link to vote for the bot on discordbots.org:\n<https://discordbots.org/bot/429024440060215296/vote>')
        
        # shard
        if msg == c+'!shard':
            await self.client.send_message(ch, str(self.shard))
        
        # custom prefix setting
        if len(msg) == 10 and msg[:9] == c+'!prefix ' and 'a' <= msg[9] <= 'z':
            await self.client.send_message(ch, 'Command prefix set to `' + msg[9] + '`!')
            config.pre[ch.id] = msg[9]
            with open('prefix.txt', 'a') as f:
                f.write(ch.id + ' ' + msg[9] + '\n')
        
        if not config.C[ch]['started']:
            # language change
            for l in config.languages:
                if msg == c+'!language '+l.lower():
                    if config.C[ch]['lang'] != l:
                        config.C[ch]['lang'] = l
                        config.C[ch]['black'] = list(eval('config.black_'+config.languages[l]))
                        config.C[ch]['white'] = list(eval('config.white_'+config.languages[l]))
                        await self.client.send_message(ch, 'Language changed to ' + l + '.')
                        await self.edit_start_msg(ch)
            
            if msg == c+'!help':
                await self.client.send_message(ch, (
                    "Use `{0}!start` to start a game of Cards Against Humanity, or `{0}!cancel` to cancel an existing one.\n"
                    "Use `{0}!commands` to bring up a list of available commands.").format(c))
            elif msg == c+'!language english':
                if config.C[ch]['lang'] != 'English':
                    config.C[ch]['lang'] = 'English'
                    config.C[ch]['black'] = config.black
                    config.C[ch]['white'] = config.white
                    await self.client.send_message(ch, 'Language changed to English.')
                    await self.edit_start_msg(ch)
            elif msg == c+'!start':
                if not config.C[ch]['playerMenu']:
                    config.C[ch]['playerMenu'] = True
                    config.C[ch]['players'].append(au)
                    s = await self.get_start_msg(ch)
                    config.C[ch]['msg'] = await self.client.send_message(ch, s)
                    output = str(len(config.C[ch]['players'])) + '/20 Players: '
                    output += ', '.join(usr.display_name for usr in config.C[ch]['players'])
                    await self.client.send_message(ch, output)
                elif 2 <= len(config.C[ch]['players']) <= 20:
                    config.C[ch]['playerMenu'] = False
                    config.C[ch]['nPlayers'] = len(config.C[ch]['players'])
                    await self.start_(ch)
                    
                    await self.client.send_message(ch,
                        'Game is starting!\n' + ' '.join(usr.mention for usr in config.C[ch]['players']))
                    
                    config.C[ch]['msg'] = None
                    await self.displayMid(ch)
            elif len(msg) > 8 and msg[:8] == c+'!setwin':
                try:
                    n = int(msg[8:].strip())
                    if n > 0:
                        config.C[ch]['win'] = n
                        await self.client.send_message(ch, 'Number of points needed to win has been set to ' + str(n) + '.')
                        await self.edit_start_msg(ch)
                except:
                    pass
            elif len(msg) > 7 and msg[:7] == c+'!timer':
                try:
                    n = int(msg[7:].strip())
                    if n >= 15:
                        config.C[ch]['timer'] = n
                        await self.client.send_message(ch, 'Idle timer set to ' + str(n) + ' seconds.')
                        await self.edit_start_msg(ch)
                    elif n == 0:
                        config.C[ch]['timer'] = n
                        await self.client.send_message(ch, 'Idle timer is now disabled.')
                        await self.edit_start_msg(ch)
                    else:
                        await self.client.send_message(ch, 'Please choose a minimum of 15 seconds.')
                except:
                    pass
            elif len(msg) > 10 and msg[:10] == c+'!settimer':
                try:
                    n = int(msg[10:].strip())
                    if n >= 15:
                        config.C[ch]['timer'] = n
                        await self.client.send_message(ch, 'Idle timer set to " + str(n) + " seconds.')
                        await self.edit_start_msg(ch)
                    elif n == 0:
                        config.C[ch]['timer'] = n
                        await self.client.send_message(ch, 'Idle timer is now disabled.')
                        await self.edit_start_msg(ch)
                    else:
                        await self.client.send_message(ch, 'Please choose a minimum of 15 seconds.')
                except:
                    pass
            elif len(msg) > 10 and msg[:10] == c+'!setblank':
                try:
                    n = int(msg[10:].strip())
                    if 0 <= n <= 30:
                        config.C[ch]['blanks'] = n
                        await self.client.send_message(ch, 'Number of blanks has been set to ' + str(n) + '.')
                        await self.edit_start_msg(ch)
                except:
                    pass
            elif msg == c+'!packs':
                output = ("**List of available packs:**\n"
                    "(pack code followed by name of pack, then number of black and white cards)\n"
                    "----------\n")
                for p in config.packs:
                    output += '**'+p+'** - ' + config.packs[p] \
                        + ' (' + str(len(eval('config.black_'+p))) + '/' + str(len(eval('config.white_'+p))) + ')\n'
                await self.client.send_message(ch, output)
                output = '\nThird party packs:\n'
                for p in config.thirdparty:
                    output += '**'+p+'** - ' + config.thirdparty[p] \
                        + ' (' + str(len(eval('config.black_'+p))) + '/' + str(len(eval('config.white_'+p))) + ')\n'
                output += ("\nUse `{0}!add <code>` to add a pack, or use `{0}!add all` to add all available packs.\n"
                    "(Note: this will only add official CAH packs; use `{0}!add thirdparty` to add all third party packs.)\n"
                    "Use `{0}!contents <code>` to see what cards are in a specific pack.").format(c)
                await self.client.send_message(ch, output)
            elif len(msg) > 10 and msg[:10] == c+'!contents':
                pk = message.content[10:].strip()
                
                # check for CardCast packs
                try:
                    b, w = api.get_deck_blacks_json(pk), api.get_deck_whites_json(pk)
                    deck_b = ['_'.join(c['text']) for c in b]
                    deck_w = [''.join(c['text']) for c in w]
                    
                    output = '**Cards in ' + api.get_deck_info_json(pk)['name'] + '** (code: ' + pk + ')**:**\n\n'
                    output += '**Black cards:** (' + str(len(deck_b)) + ')\n'
                    for c in deck_b:
                        output += '- ' + c + '\n'
                        if len(output) > 1500:
                            await self.client.send_message(ch, output.replace('_','\_'*3))
                            output = ''
                    output += '\n**White cards:** (' + str(len(deck_w)) + ')\n'
                    for c in deck_w:
                        output += '- ' + c + '\n'
                        if len(output) > 1500:
                            await self.client.send_message(ch, output.replace('_','\_'*3))
                            output = ''
                    await self.client.send_message(ch, output.replace('_','\_'*3))
                    
                    return
                except:
                    pass
                
                # check built-in packs
                pk = pk.lower()
                if pk in config.packs or pk in config.thirdparty:
                    output = ''
                    if pk in config.packs:
                        output = '**Cards in ' + config.packs[pk] + ':**\n\n'
                    elif pk in config.thirdparty:
                        output = '**Cards in ' + config.thirdparty[pk] + ':**\n\n'
                    
                    output += '**Black cards:** (' + str(len(eval('config.black_'+pk))) + ')\n'
                    for c in eval('config.black_'+pk):
                        output += '- ' + c + '\n'
                        if len(output) > 1500:
                            await self.client.send_message(ch, output.replace('_','\_'*3))
                            output = ''
                    output += '\n**White cards:** (' + str(len(eval('config.white_'+pk))) + ')\n'
                    for c in eval('config.white_'+pk):
                        output += '- ' + c + '\n'
                        if len(output) > 1500:
                            await self.client.send_message(ch, output.replace('_','\_'*3))
                            output = ''
                    await self.client.send_message(ch, output.replace('_','\_'*3))
            elif msg == c+'!cancel':
                if config.C[ch]['playerMenu']:
                    config.C[ch]['playerMenu'] = False
                    config.C[ch]['players'] = []
                    await self.client.send_message(ch, 'Game cancelled!')
            
            if config.C[ch]['playerMenu']:
                curr = len(config.C[ch]['players'])
                if msg == c+'!join':
                    if au not in config.C[ch]['players']:
                        config.C[ch]['players'].append(au)
                elif msg == c+'!leave':
                    if au in config.C[ch]['players']:
                        config.C[ch]['players'].remove(au)
                if curr != len(config.C[ch]['players']):
                    output = str(len(config.C[ch]['players'])) + '/20 Players: '
                    output += ', '.join(usr.display_name for usr in config.C[ch]['players'])
                    await self.client.send_message(ch, output)
                if len(msg) > 6 and msg[:6] == c+'!add ' and config.C[ch]['lang'] == 'English':
                    await self.addPack(ch, message.content[6:])
                if len(msg) > 9 and msg[:9] == c+'!remove ' and config.C[ch]['lang'] == 'English':
                    await self.removePack(ch, message.content[9:])
                elif len(msg) > 5 and msg[:5] == c+'!rm ' and config.C[ch]['lang'] == 'English':
                    await self.removePack(ch, message.content[5:])
        else:
            if msg == c+'!help':
                await self.client.send_message(ch, (
                    "To play white cards, use `{0}!play` followed by the letters next to the cards you want to play. "
                    "For example, `{0}!play b` would play card B, and `{0}!play df` would play cards D and F.\n"
                    "If you're the czar, react with the letter of your choice once everyone has played their cards.\n"
                    "To reset an ongoing game, use `{0}!reset`.\n"
                    "To leave an ongoing game, use `{0}!leave` or `{0}!quit`.\n"
                    "To join an ongoing game, use `{0}!join`.\n"
                    "To kick an AFK player, use `{0}!kick <player>`.").format(c))
            
            # player commands
            if au in config.C[ch]['players']:
                if msg == c+'!display':
                    config.C[ch]['msg'] = None
                    await self.displayMid(ch)
                elif msg == c+'!leave' or msg == c+'!quit':
                    if not config.done(ch):
                        await self.removePlayer(ch, au)
                    else:
                        await self.client.send_message(ch, 'Please wait for the czar to pick a card before leaving.')
                elif len(msg) > 7 and msg[:7] == c+'!kick ':
                    mt = message.content[7:].strip() # player to kick
                    if mt == au.mention:
                        await self.client.send_message(ch, 'You cannot kick yourself. To leave the game, use `'+c+'!leave`.')
                    else:
                        for i in range(len(config.C[ch]['players'])):
                            p = config.C[ch]['players'][i]
                            if mt == p.mention:
                                if not config.C[ch]['played'][i]:
                                    config.C[ch]['kick'][config.C[ch]['players'].index(au)] = p.mention
                                    cnt = config.C[ch]['kick'].count(p.mention)
                                    await self.client.send_message(ch, au.mention + ' has voted to kick ' + p.mention + '. ' \
                                        + str(cnt) + '/' + str(config.C[ch]['nPlayers']-1) + ' votes needed')
                                    if cnt == config.C[ch]['nPlayers'] - 1:
                                        await self.client.send_message(ch, p.mention + ' has been kicked from the game.')
                                        await self.removePlayer(ch, p, kick=True)
                                else:
                                    await self.client.send_message(ch, 'This player has already played and cannot be kicked.')
                                
                                break
                elif msg == c+'!reset':
                    await config.reset(ch)
                    await self.client.send_message(ch, 'Game reset!')
            else:
                if msg == c+'!join':
                    if not config.done(ch):
                        await self.addPlayer(ch, au)
                    else:
                        await self.client.send_message(ch, 'Please wait for the czar to pick an answer before joining.')
            
            # playing cards
            if len(msg) > 6 and msg[:6] == c+'!play':
                await self.play(ch,au,msg[6:])
                try:
                    await self.client.delete_message(message)
                except:
                    pass
            elif len(msg) > 4 and msg[:4] == c+'!p ':
                await self.play(ch,au,msg[4:])
                try:
                    await self.client.delete_message(message)
                except:
                    pass
            
            # admin override
            if au.id == '252249185112293376' or au.permissions_in(ch).administrator:
                if msg == c+'!display':
                    config.C[ch]['msg'] = None
                    await self.displayMid(ch)
                elif msg == c+'!reset':
                    await config.reset(ch)
                    await self.client.send_message(ch, 'Game reset!')
    
    async def on_reaction_add(self, reaction, user):
        ch = reaction.message.channel
        
        if (ch not in config.C) or (not config.C[ch]['started']):
            return
        
        czar = config.C[ch]['players'][config.C[ch]['pov']]
        letters = ['\U0001F1E6','\U0001F1E7','\U0001F1E8','\U0001F1E9','\U0001F1EA',
                   '\U0001F1EB','\U0001F1EC','\U0001F1ED','\U0001F1EE','\U0001F1EF'][:config.C[ch]['nPlayers']-1]
    
        if config.done(ch) and config.C[ch]['msg'] != None and reaction.message.content == config.C[ch]['msg'].content and czar == user:
            if reaction.emoji in letters:
                try:
                    p = config.C[ch]['mid'][letters.index(reaction.emoji)][1]
    
                    config.C[ch]['score'][p] += 1
                
                    msg = czar.display_name + ' selected ' + 'ABCDEFGHIJ'[letters.index(reaction.emoji)] + '.\n'
                    msg += config.C[ch]['players'][p].display_name + ' wins the round!'
                    await self.client.send_message(ch, msg)
                    await self.pass_(ch)
                    
                    if config.C[ch]['win'] in config.C[ch]['score']:
                        await self.displayWinners(ch)
                        await config.reset(ch)
                except:
                    print('\nError with answer selection\n' + time.asctime() + '\n')
    
    async def timer_check(self):
        await self.client.wait_until_ready()
        
        while not self.client.is_closed:
            channels = list(config.C.keys())
            for ch in channels:
                if config.C[ch]['started']:
                    if config.C[ch]['timer'] != 0 and time.time() - config.C[ch]['time'] >= config.C[ch]['timer']:
                        if config.done(ch):
                            try:
                                await self.client.send_message(ch, "**TIME'S UP!**")
                                
                                # pick random letter
                                letter = random.randint(0, len(config.C[ch]['mid'])-1)
                                
                                p = config.C[ch]['mid'][letter][1]
                
                                config.C[ch]['score'][p] += 1
                            
                                msg = 'The bot randomly selected ' + 'ABCDEFGHIJ'[letter] + '.\n'
                                msg += config.C[ch]['players'][p].display_name + ' wins the round!'
                                await self.client.send_message(ch, msg)
                                await self.pass_(ch)
                                
                                if config.C[ch]['win'] in config.C[ch]['score']:
                                    await self.displayWinners(ch)
                                    await config.reset(ch)
                            except:
                                print('\nError with answer selection\n' + time.asctime() + '\n')
                        else:
                            await self.client.send_message(ch, "**TIME'S UP!**\nFor those who haven't played, cards will be automatically selected.")
                            
                            N = config.nCards(ch)
                            for p in range(len(config.C[ch]['players'])):
                                if not config.C[ch]['played'][p] and config.C[ch]['pov'] != p:
                                    cards = ''
                                    for c in range(len(config.C[ch]['hands'][p])):
                                        if config.C[ch]['hands'][p][c]:
                                            cards += 'abcdefghijkl'[c]
                                            if len(cards) == N:
                                                await self.play(ch, config.C[ch]['players'][p], cards)
                                                break
                            
            await asyncio.sleep(2)
    
    async def blank_check(self):
        await self.client.wait_until_ready()
        
        while not self.client.is_closed:
            async with aiosqlite.connect('messages{0}.db'.format(self.shard)) as conn:
                C = await conn.cursor()
                
                await C.execute("""select * from Messages""")
                msgs = await C.fetchall()
                await C.execute("""delete from Messages""")
                await conn.commit()
                
            if len(msgs):
                for x in msgs:
                    for au in config.P:
                        if au.id == x[0]:
                            for c in config.P[au]: # check all channels that user is in
                                if config.C[c]['started'] and au in config.C[c]['players']: # check that user is currently playing
                                    i = config.C[c]['players'].index(au)
                                    if '' in config.C[c]['hands'][i]: # check that player has a blank
                                        j = config.C[c]['hands'][i].index('')
                                        config.C[c]['hands'][i][j] = x[1]
                                        await self.sendHand(c, i)
                                        break
            
            await asyncio.sleep(3)
    
    def run(self):
        self.client.loop.create_task(self.timer_check())
        with open("config.yaml", 'r') as stream:
            try:
                cfg = yaml.load(stream)
            except yaml.YAMLError as exc:
                print(exc)
        discord_bot_token = cfg['token']
        self.client.run(discord_bot_token)
