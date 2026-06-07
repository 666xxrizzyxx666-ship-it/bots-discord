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
bot = commands.Bot(command_prefix="?", intents=intents)
tree = bot.tree

WARNS_FILE = "warns_staff.json"

def load(file):
    if os.path.exists(file):
        with open(file) as f:
            return json.load(f)
    return {}

def save(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

warns = load(WARNS_FILE)

# ─── Trackers ──────────────────────────────────────────────
spam_tracker = defaultdict(list)        # messages par user
mention_tracker = defaultdict(list)     # mentions par user
join_tracker = []                       # joins récents pour anti-raid
raid_mode = False

# ─── Mots interdits ────────────────────────────────────────
MOTS_INTERDITS = [
    "nique", "fdp", "pute", "salope", "connard", "enculé", "batard",
    "ntm", "ta gueule", "fils de", "racist", "nazisme", "hitler",
    "nègre", "sale arab", "sale noir", "pd ", " pd", "tapette"
]

# ─── Liens suspects ────────────────────────────────────────
DOMAINES_SUSPECTS = [
    "bit.ly", "tinyurl", "discord.gift", "discordnitro", "free-nitro",
    "steamcommunity.ru", "csgo-skins", "freevbucks", "nitro-free"
]

# ─── Log helper ────────────────────────────────────────────
async def log(guild, title, color, **fields):
    ch = guild.get_channel(LOG_CHANNEL)
    if not ch:
        return
    embed = discord.Embed(title=title, color=color, timestamp=datetime.now())
    for name, value in fields.items():
        embed.add_field(name=name, value=str(value)[:500], inline=True)
    embed.set_footer(text="Fanatic Ressel • Auto-Mod")
    await ch.send(embed=embed)

# ─── Auto-warn helper ──────────────────────────────────────
async def auto_warn(member, raison):
    uid = str(member.id)
    if uid not in warns:
        warns[uid] = []
    warns[uid].append({
        "raison": raison,
        "par": "Auto-Mod",
        "date": datetime.now().strftime("%d/%m/%Y %H:%M")
    })
    save(WARNS_FILE, warns)
    count = len(warns[uid])

    await log(member.guild, "⚠️ Auto-Warn", 0xFF9900,
               Membre=member.mention, Raison=raison, Total=f"{count}/3")

    if count >= 3:
        await member.kick(reason="3 avertissements automatiques")
        await log(member.guild, "🦵 Auto-Kick (3 warns)", 0xFF3355,
                   Membre=str(member), Raison="3 avertissements auto")
    elif count == 2:
        role = discord.utils.get(member.guild.roles, name="Muted")
        if not role:
            role = await member.guild.create_role(name="Muted")
            for ch in member.guild.channels:
                await ch.set_permissions(role, send_messages=False, speak=False)
        await member.add_roles(role)
        await asyncio.sleep(300)  # mute 5 minutes
        await member.remove_roles(role)
        await log(member.guild, "🔇 Auto-Mute 5min (2 warns)", 0xAA44FF,
                   Membre=member.mention)

# ─── Events ────────────────────────────────────────────────
@bot.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"✅ Bot Staff connecté : {bot.user}")
    check_raid_mode.start()

@bot.event
async def on_member_join(member):
    global raid_mode

    # Anti-raid : compte les joins dans les 10 dernières secondes
    now = datetime.now().timestamp()
    join_tracker.append(now)
    recent = [t for t in join_tracker if now - t < 10]
    join_tracker.clear()
    join_tracker.extend(recent)

    # Si 5+ membres rejoignent en 10 secondes = raid détecté
    if len(recent) >= 5 and not raid_mode:
        raid_mode = True
        guild = member.guild
        await log(guild, "🚨 RAID DÉTECTÉ — LOCKDOWN ACTIVÉ", 0xFF0000,
                   Membres_récents=len(recent),
                   Action="Tous les salons verrouillés pendant 5 minutes")
        for channel in guild.text_channels:
            try:
                await channel.set_permissions(guild.default_role, send_messages=False)
            except:
                pass

    # Compte récent = moins de 7 jours
    age = (datetime.now() - member.created_at.replace(tzinfo=None)).days
    if age < 7:
        await log(member.guild, "⚠️ Compte suspect à l'entrée", 0xFF6B35,
                   Membre=member.mention,
                   Age_compte=f"{age} jours",
                   Action="Surveillance renforcée")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if message.author.guild_permissions.administrator:
        await bot.process_commands(message)
        return

    content = message.content.lower()
    now = datetime.now().timestamp()
    uid = str(message.author.id)

    # ── Anti-spam ──
    spam_tracker[uid].append(now)
    spam_tracker[uid] = [t for t in spam_tracker[uid] if now - t < 5]

    if len(spam_tracker[uid]) >= 6:
        await message.delete()
        await auto_warn(message.author, "Spam détecté automatiquement")
        try:
            await message.channel.send(
                f"⚠️ {message.author.mention} **spam détecté** — avertissement automatique.",
                delete_after=5)
        except:
            pass
        spam_tracker[uid].clear()
        return

    # ── Anti-mentions abusives ──
    mention_count = len(message.mentions) + len(message.role_mentions)
    if mention_count >= 5:
        await message.delete()
        await auto_warn(message.author, f"Mentions abusives ({mention_count} mentions)")
        await message.channel.send(
            f"⚠️ {message.author.mention} **mentions abusives** — avertissement automatique.",
            delete_after=5)
        return

    # ── Anti-insultes ──
    for mot in MOTS_INTERDITS:
        if mot in content:
            await message.delete()
            await auto_warn(message.author, f"Langage interdit : `{mot}`")
            await message.channel.send(
                f"⚠️ {message.author.mention} **langage interdit** — avertissement automatique.",
                delete_after=5)
            return

    # ── Anti-liens suspects ──
    urls = re.findall(r'https?://[^\s]+', content)
    for url in urls:
        for domaine in DOMAINES_SUSPECTS:
            if domaine in url:
                await message.delete()
                await auto_warn(message.author, f"Lien suspect : `{domaine}`")
                await message.channel.send(
                    f"⚠️ {message.author.mention} **lien suspect supprimé** — avertissement automatique.",
                    delete_after=5)
                return

    # ── Anti-pub Discord ──
    if "discord.gg/" in content or "discord.com/invite/" in content:
        if not message.author.guild_permissions.manage_guild:
            await message.delete()
            await auto_warn(message.author, "Publicité Discord non autorisée")
            await message.channel.send(
                f"⚠️ {message.author.mention} **publicité interdite** — avertissement automatique.",
                delete_after=5)
            return

    # ── Anti-messages en majuscules (CAPS) ──
    if len(content) > 10:
        caps = sum(1 for c in message.content if c.isupper())
        if caps / len(message.content) > 0.7:
            await message.delete()
            await message.channel.send(
                f"⚠️ {message.author.mention} évite les messages en majuscules.",
                delete_after=5)
            return

    await bot.process_commands(message)

@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return
    await log(message.guild, "🗑️ Message supprimé", 0xFF9900,
               Auteur=message.author.mention,
               Salon=message.channel.mention,
               Contenu=message.content[:500] or "vide")

@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.content == after.content:
        return
    await log(before.guild, "✏️ Message modifié", 0xAA44FF,
               Auteur=before.author.mention,
               Avant=before.content[:300] or "vide",
               Après=after.content[:300] or "vide")

@bot.event
async def on_member_remove(member):
    await log(member.guild, "❌ Membre parti", 0xFF3355,
               Membre=str(member), ID=member.id)

@bot.event
async def on_member_ban(guild, user):
    await log(guild, "🔨 Membre banni", 0xFF0000,
               Membre=str(user), ID=user.id)

# ─── Anti-raid : désactive le lockdown après 5 min ─────────
@tasks.loop(seconds=30)
async def check_raid_mode():
    global raid_mode
    if raid_mode:
        guild = bot.get_guild(GUILD_ID)
        if guild:
            for channel in guild.text_channels:
                try:
                    role = guild.get_role(ROLE_MEMBRE)
                    if role:
                        await channel.set_permissions(role, send_messages=True)
                except:
                    pass
            raid_mode = False
            await log(guild, "✅ Lockdown levé", 0x00FF88,
                       Info="Le mode raid est désactivé, serveur de nouveau accessible")

# ─── Commandes manuelles staff ─────────────────────────────
@tree.command(name="warn", description="Avertir manuellement un membre",
              guild=discord.Object(id=GUILD_ID))
@app_commands.describe(membre="Le membre", raison="Raison")
async def warn(interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune raison"):
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("❌ Pas autorisé.", ephemeral=True)
        return
    await auto_warn(membre, f"[Manuel] {raison}")
    await interaction.response.send_message(f"✅ {membre.mention} averti.", ephemeral=True)

@tree.command(name="clearwarns", description="Effacer les warns d'un membre",
              guild=discord.Object(id=GUILD_ID))
@app_commands.describe(membre="Le membre")
async def clearwarns(interaction: discord.Interaction, membre: discord.Member):
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("❌ Pas autorisé.", ephemeral=True)
        return
    warns[str(membre.id)] = []
    save(WARNS_FILE, warns)
    await interaction.response.send_message(f"✅ Warns de {membre.mention} effacés.", ephemeral=True)

@tree.command(name="kick", description="Expulser un membre",
              guild=discord.Object(id=GUILD_ID))
@app_commands.describe(membre="Le membre", raison="Raison")
async def kick(interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune raison"):
    if not interaction.user.guild_permissions.kick_members:
        await interaction.response.send_message("❌ Pas autorisé.", ephemeral=True)
        return
    await membre.kick(reason=raison)
    await interaction.response.send_message(f"🦵 {membre.mention} expulsé.")
    await log(interaction.guild, "🦵 Kick manuel", 0xFF6B35,
               Membre=str(membre), Par=interaction.user.mention, Raison=raison)

@tree.command(name="ban", description="Bannir un membre",
              guild=discord.Object(id=GUILD_ID))
@app_commands.describe(membre="Le membre", raison="Raison")
async def ban(interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune raison"):
    if not interaction.user.guild_permissions.ban_members:
        await interaction.response.send_message("❌ Pas autorisé.", ephemeral=True)
        return
    await membre.ban(reason=raison)
    await interaction.response.send_message(f"🔨 {membre.mention} banni.")
    await log(interaction.guild, "🔨 Ban manuel", 0xFF0000,
               Membre=str(membre), Par=interaction.user.mention, Raison=raison)

@tree.command(name="lockdown", description="Verrouiller tout le serveur",
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

@tree.command(name="unlockdown", description="Déverrouiller tout le serveur",
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
