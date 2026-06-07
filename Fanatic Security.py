import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
from datetime import datetime, timedelta
import asyncio
import re
from collections import defaultdict

TOKEN = ""

GUILD_ID = 1513108386722480211
LOG_CHANNEL = 1513141801806987356
ROLE_MEMBRE = 1513113125883216032

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ─── Fichiers ──────────────────────────────────────────────
BLACKLIST_FILE = "blacklist.json"
VERIFIED_FILE  = "verified.json"
CONFIG_FILE    = "security_config.json"

def load(file):
    if os.path.exists(file):
        with open(file) as f:
            return json.load(f)
    return {}

def save(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

blacklist = load(BLACKLIST_FILE)
verified  = load(VERIFIED_FILE)
config    = load(CONFIG_FILE)

# ─── Trackers ──────────────────────────────────────────────
join_tracker        = []
raid_mode           = False
raid_mode_start     = None
invite_tracker      = defaultdict(int)
suspicious_tracker  = defaultdict(list)
dm_tracker          = defaultdict(list)

# ─── Log ───────────────────────────────────────────────────
async def log(guild, title, color, **fields):
    ch = guild.get_channel(LOG_CHANNEL)
    if not ch:
        return
    embed = discord.Embed(title=title, color=color, timestamp=datetime.now())
    for name, value in fields.items():
        embed.add_field(name=name, value=str(value)[:500], inline=True)
    embed.set_footer(text="Fanatic Security • Auto-Protect")
    await ch.send(embed=embed)

# ─── Events ────────────────────────────────────────────────
@bot.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"✅ Bot Security connecté : {bot.user}")
    check_raid_unlock.start()
    check_suspicious.start()
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name="🔒 Protection active"),
        status=discord.Status.dnd
    )

# ─── Anti-Raid ─────────────────────────────────────────────
@bot.event
async def on_member_join(member):
    global raid_mode, raid_mode_start

    now = datetime.now().timestamp()

    # Blacklist check
    if str(member.id) in blacklist:
        await member.ban(reason="Blacklisté — Fanatic Security")
        await log(member.guild, "🚫 Blacklist — Ban automatique", 0xFF0000,
                   Membre=str(member), ID=member.id)
        return

    # Compte très récent (moins de 3 jours)
    age = (datetime.now() - member.created_at.replace(tzinfo=None)).days
    if age < 3:
        await member.kick(reason="Compte trop récent — moins de 3 jours")
        await log(member.guild, "⚠️ Compte trop récent — Kick auto", 0xFF6B35,
                   Membre=str(member), Age=f"{age} jours", Action="Kick automatique")
        return

    # Compte suspect (moins de 7 jours) — surveillance
    if age < 7:
        suspicious_tracker[str(member.id)].append(now)
        await log(member.guild, "⚠️ Compte suspect — Surveillance", 0xFFD700,
                   Membre=member.mention, Age=f"{age} jours")

    # Anti-raid — 5 joins en 10 secondes
    join_tracker.append(now)
    recent = [t for t in join_tracker if now - t < 10]
    join_tracker.clear()
    join_tracker.extend(recent)

    if len(recent) >= 5 and not raid_mode:
        raid_mode = True
        raid_mode_start = now
        guild = member.guild

        # Lockdown tous les salons
        for channel in guild.text_channels:
            try:
                await channel.set_permissions(guild.default_role, send_messages=False)
                await channel.set_permissions(guild.get_role(ROLE_MEMBRE),
                                               send_messages=False)
            except:
                pass

        # Kick tous les nouveaux du raid
        for m in guild.members:
            join_delta = (datetime.now() - m.joined_at.replace(tzinfo=None)).seconds
            if join_delta < 30 and not m.bot and not m.guild_permissions.administrator:
                try:
                    await m.kick(reason="Anti-raid — Fanatic Security")
                except:
                    pass

        await log(guild, "🚨 RAID DÉTECTÉ — LOCKDOWN ACTIVÉ", 0xFF0000,
                   Joins_récents=len(recent),
                   Action="Lockdown + kick des raiders",
                   Durée="10 minutes")

        # Alerte dans le salon logs
        ch = guild.get_channel(LOG_CHANNEL)
        if ch:
            await ch.send("@everyone 🚨 **RAID DÉTECTÉ** — Lockdown activé pendant 10 minutes !")

# ─── Unlock automatique après 10 minutes ───────────────────
@tasks.loop(seconds=30)
async def check_raid_unlock():
    global raid_mode, raid_mode_start
    if raid_mode and raid_mode_start:
        if datetime.now().timestamp() - raid_mode_start > 600:
            guild = bot.get_guild(GUILD_ID)
            if guild:
                role = guild.get_role(ROLE_MEMBRE)
                for channel in guild.text_channels:
                    try:
                        if role:
                            await channel.set_permissions(role, send_messages=True)
                    except:
                        pass
                raid_mode = False
                raid_mode_start = None
                await log(guild, "✅ Lockdown levé automatiquement", 0x00FF88,
                           Info="Serveur de nouveau accessible")

# ─── Détection comportements suspects ──────────────────────
@tasks.loop(minutes=5)
async def check_suspicious():
    now = datetime.now().timestamp()
    for uid in list(suspicious_tracker.keys()):
        suspicious_tracker[uid] = [t for t in suspicious_tracker[uid] if now - t < 3600]
        if not suspicious_tracker[uid]:
            del suspicious_tracker[uid]

# ─── Anti-phishing / liens malveillants ────────────────────
PHISHING_PATTERNS = [
    r'discord\.gift/[a-zA-Z0-9]+',
    r'discordnitro[a-zA-Z0-9\-\.]+',
    r'free[-_]?nitro[a-zA-Z0-9\-\.]+',
    r'steamcommunity\.[a-z]{2,}/[a-zA-Z0-9]+',
    r'csgo[-_]?skins',
    r'free[-_]?vbucks',
    r'nitro[-_]?free',
    r'airdrop[-_]?crypto',
    r'claim[-_]?your',
]

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if message.author.guild_permissions.administrator:
        await bot.process_commands(message)
        return

    content = message.content.lower()

    # Anti-phishing
    for pattern in PHISHING_PATTERNS:
        if re.search(pattern, content):
            await message.delete()
            await message.channel.send(
                f"🚫 {message.author.mention} **lien de phishing détecté et supprimé**.",
                delete_after=5)
            await log(message.guild, "🚫 Phishing détecté", 0xFF0000,
                       Membre=message.author.mention,
                       Pattern=pattern,
                       Action="Message supprimé + warn")
            try:
                await message.author.send(
                    "⚠️ Ton message a été supprimé sur **Fanatic Ressel** car il contenait un lien suspect. "
                    "Si ton compte a été compromis, change ton mot de passe Discord immédiatement.")
            except:
                pass
            return

    # Détection token grabber / IP logger
    suspicious_domains = ["grabify", "iplogger", "blasze", "linkvertise", "bit.ly", "tinyurl"]
    for domain in suspicious_domains:
        if domain in content:
            await message.delete()
            await message.channel.send(
                f"🚫 {message.author.mention} **lien suspect supprimé**.",
                delete_after=5)
            await log(message.guild, "🚫 IP Logger / Token Grabber", 0xFF0000,
                       Membre=message.author.mention, Domaine=domain)
            return

    await bot.process_commands(message)

# ─── Détection token dans les messages ─────────────────────
TOKEN_PATTERN = re.compile(r'[MN][a-zA-Z0-9]{23}\.[a-zA-Z0-9_-]{6}\.[a-zA-Z0-9_-]{27,}')

@bot.event
async def on_message_edit(before, after):
    if after.author.bot:
        return
    if TOKEN_PATTERN.search(after.content):
        await after.delete()
        await log(after.guild, "🔑 Token Discord détecté et supprimé", 0xFF0000,
                   Membre=after.author.mention,
                   Action="Message supprimé automatiquement")

# ─── Anti-DM spam ──────────────────────────────────────────
@bot.event
async def on_member_update(before, after):
    pass

# ─── Commandes staff ───────────────────────────────────────
@tree.command(name="blacklist", description="Blacklister un utilisateur",
              guild=discord.Object(id=GUILD_ID))
@app_commands.describe(membre="Le membre", raison="Raison")
async def blacklist_add(interaction: discord.Interaction, membre: discord.Member,
                         raison: str = "Aucune raison"):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Pas autorisé.", ephemeral=True)
        return
    blacklist[str(membre.id)] = {"raison": raison, "par": str(interaction.user),
                                   "date": datetime.now().strftime("%d/%m/%Y")}
    save(BLACKLIST_FILE, blacklist)
    await membre.ban(reason=f"Blacklist : {raison}")
    await interaction.response.send_message(f"🚫 {membre.mention} blacklisté et banni.")
    await log(interaction.guild, "🚫 Blacklist ajout", 0xFF0000,
               Membre=str(membre), Par=interaction.user.mention, Raison=raison)

@tree.command(name="unblacklist", description="Retirer de la blacklist",
              guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user_id="ID de l'utilisateur")
async def unblacklist(interaction: discord.Interaction, user_id: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Pas autorisé.", ephemeral=True)
        return
    if user_id in blacklist:
        del blacklist[user_id]
        save(BLACKLIST_FILE, blacklist)
        await interaction.guild.unban(discord.Object(id=int(user_id)))
        await interaction.response.send_message(f"✅ {user_id} retiré de la blacklist.")
    else:
        await interaction.response.send_message("❌ Pas dans la blacklist.", ephemeral=True)

@tree.command(name="security_status", description="Statut de la sécurité",
              guild=discord.Object(id=GUILD_ID))
async def security_status(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Pas autorisé.", ephemeral=True)
        return
    embed = discord.Embed(title="🔒 Statut Sécurité — Fanatic Ressel", color=0x00FF88,
                           timestamp=datetime.now())
    embed.add_field(name="Mode Raid", value="🚨 ACTIF" if raid_mode else "✅ Inactif")
    embed.add_field(name="Blacklist", value=f"{len(blacklist)} entrées")
    embed.add_field(name="Comptes suspects", value=f"{len(suspicious_tracker)} surveillés")
    embed.add_field(name="Anti-phishing", value="✅ Actif")
    embed.add_field(name="Anti-raid", value="✅ Actif")
    embed.add_field(name="Détection tokens", value="✅ Actif")
    await interaction.response.send_message(embed=embed)

@tree.command(name="lockdown", description="Lockdown manuel du serveur",
              guild=discord.Object(id=GUILD_ID))
async def lockdown(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Pas autorisé.", ephemeral=True)
        return
    for channel in interaction.guild.text_channels:
        try:
            await channel.set_permissions(interaction.guild.default_role, send_messages=False)
        except:
            pass
    await interaction.response.send_message("🔒 Serveur verrouillé.")
    await log(interaction.guild, "🔒 Lockdown manuel", 0xFF0000,
               Par=interaction.user.mention)

@tree.command(name="unlockdown", description="Lever le lockdown",
              guild=discord.Object(id=GUILD_ID))
async def unlockdown(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Pas autorisé.", ephemeral=True)
        return
    role = interaction.guild.get_role(ROLE_MEMBRE)
    for channel in interaction.guild.text_channels:
        try:
            if role:
                await channel.set_permissions(role, send_messages=True)
        except:
            pass
    await interaction.response.send_message("🔓 Serveur déverrouillé.")
    await log(interaction.guild, "🔓 Unlockdown", 0x00FF88,
               Par=interaction.user.mention)

bot.run(TOKEN)
