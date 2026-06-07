import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from datetime import datetime
import asyncio

TOKEN = ""

GUILD_ID = 1513108386722480211
ROLE_MEMBRE = 1513113125883216032

CHANNELS = {
    "regles": 1513110628112400464,
    "nouveautes": 1513110903514730676,
    "prix_du_moment": 1513110932744573018,
    "stock_disponible": 1513110960947204107,
    "drops_a_venir": 1513110992173928518,
    "alertes_restocks": 1513111015498190878,
    "sneakers": 1513111096439865374,
    "vetements": 1513111122037706842,
    "parfums": 1513111147832938506,
    "tech": 1513111170876440628,
    "accessoires": 1513111196692123749,
    "questions": 1513111313218535494,
    "general": 1513111653858676817,
    "avis_clients": 1513111675627376821,
    "ouvrir_ticket": 1513111742673064006,
    "bienvenue": 1513144628826869941,
}

CATEGORIES = {
    "sneakers": CHANNELS["sneakers"],
    "vêtements": CHANNELS["vetements"],
    "parfums": CHANNELS["parfums"],
    "tech": CHANNELS["tech"],
    "accessoires": CHANNELS["accessoires"],
}

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

TICKETS_FILE = "tickets_fanatic.json"

def load_tickets():
    if os.path.exists(TICKETS_FILE):
        with open(TICKETS_FILE) as f:
            return json.load(f)
    return {}

def save_tickets(data):
    with open(TICKETS_FILE, "w") as f:
        json.dump(data, f, indent=2)

tickets = load_tickets()

@bot.event
async def on_ready():
    bot.add_view(AcceptRulesView())
    bot.add_view(TicketView())
    bot.add_view(CloseTicketView())
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"✅ Bot connecté : {bot.user}")
    await bot.change_presence(activity=discord.Game(name="Fanatic Ressel 🔥"))

@bot.event
async def on_member_join(member):
    guild = member.guild
    role = guild.get_role(ROLE_MEMBRE)
    ch = guild.get_channel(CHANNELS["bienvenue"])
    if ch:
        embed = discord.Embed(
            title="Bienvenue sur Fanatic Ressel ! 🔥",
            description=f"{member.mention} vient de rejoindre le serveur.\n\nVa dans le salon règles et accepte les règles pour accéder au serveur !",
            color=0x7B2FBE,
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
        embed.set_footer(text=f"Membre #{guild.member_count}")
        await ch.send(embed=embed)

@tree.command(name="deal", description="Poster un deal dans une catégorie",
              guild=discord.Object(id=GUILD_ID))
@app_commands.describe(
    categorie="La catégorie du deal",
    titre="Le titre du produit",
    prix="Le prix du produit",
    description="Description du produit",
    lien="Lien pour commander (optionnel)",
    image="URL de l'image (optionnel)"
)
@app_commands.choices(categorie=[
    app_commands.Choice(name="Sneakers", value="sneakers"),
    app_commands.Choice(name="Vêtements", value="vêtements"),
    app_commands.Choice(name="Parfums", value="parfums"),
    app_commands.Choice(name="Tech", value="tech"),
    app_commands.Choice(name="Accessoires", value="accessoires"),
])
async def deal(interaction: discord.Interaction, categorie: str, titre: str,
               prix: str, description: str, lien: str = None, image: str = None):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Pas autorisé.", ephemeral=True)
        return
    channel_id = CATEGORIES.get(categorie)
    ch = interaction.guild.get_channel(channel_id)
    color_map = {"sneakers": 0x3498DB, "vêtements": 0xE74C3C,
                 "parfums": 0x9B59B6, "tech": 0x2ECC71, "accessoires": 0xF39C12}
    emoji_map = {"sneakers": "👟", "vêtements": "👔",
                 "parfums": "🧴", "tech": "📱", "accessoires": "👜"}
    embed = discord.Embed(
        title=f"{emoji_map[categorie]} {titre}",
        description=description,
        color=color_map.get(categorie, 0x7B2FBE),
        timestamp=datetime.now()
    )
    embed.add_field(name="💰 Prix", value=f"**{prix}**", inline=True)
    embed.add_field(name="📦 Catégorie", value=categorie.capitalize(), inline=True)
    if lien:
        embed.add_field(name="🛒 Commander", value=f"[Clique ici]({lien})", inline=False)
    if image:
        embed.set_image(url=image)
    embed.set_footer(text="Fanatic Ressel • Vente - Qualité - Confiance")
    await ch.send(embed=embed)
    ch_new = interaction.guild.get_channel(CHANNELS["nouveautes"])
    if ch_new:
        await ch_new.send(embed=embed)
    await interaction.response.send_message(f"✅ Deal posté dans {ch.mention} !", ephemeral=True)

@tree.command(name="drop", description="Annoncer un drop à venir",
              guild=discord.Object(id=GUILD_ID))
@app_commands.describe(titre="Nom du produit", date="Date du drop",
                        description="Description", image="URL image (optionnel)")
async def drop(interaction: discord.Interaction, titre: str, date: str,
               description: str, image: str = None):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Pas autorisé.", ephemeral=True)
        return
    ch = interaction.guild.get_channel(CHANNELS["drops_a_venir"])
    embed = discord.Embed(title=f"📢 DROP À VENIR — {titre}", description=description,
                           color=0xFF6B35, timestamp=datetime.now())
    embed.add_field(name="📅 Date", value=f"**{date}**", inline=True)
    if image:
        embed.set_image(url=image)
    embed.set_footer(text="Fanatic Ressel • Restez connectés 🔥")
    await ch.send("@everyone", embed=embed)
    await interaction.response.send_message("✅ Drop annoncé !", ephemeral=True)

@tree.command(name="restock", description="Annoncer un restock",
              guild=discord.Object(id=GUILD_ID))
@app_commands.describe(produit="Nom du produit", quantite="Quantité dispo", prix="Prix")
async def restock(interaction: discord.Interaction, produit: str, quantite: str, prix: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Pas autorisé.", ephemeral=True)
        return
    ch = interaction.guild.get_channel(CHANNELS["alertes_restocks"])
    embed = discord.Embed(title=f"🔔 RESTOCK — {produit}",
                           description=f"**{produit}** est de nouveau disponible !",
                           color=0x00FF88, timestamp=datetime.now())
    embed.add_field(name="📦 Quantité", value=quantite, inline=True)
    embed.add_field(name="💰 Prix", value=prix, inline=True)
    embed.set_footer(text="Fanatic Ressel • Vite avant rupture !")
    await ch.send("@everyone", embed=embed)
    await interaction.response.send_message("✅ Restock annoncé !", ephemeral=True)

@tree.command(name="promo", description="Poster une promo limitée",
              guild=discord.Object(id=GUILD_ID))
@app_commands.describe(produit="Nom du produit", prix_normal="Prix normal",
                        prix_promo="Prix promo", duree="Durée", description="Description")
async def promo(interaction: discord.Interaction, produit: str, prix_normal: str,
                prix_promo: str, duree: str, description: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Pas autorisé.", ephemeral=True)
        return
    ch = interaction.guild.get_channel(CHANNELS["prix_du_moment"])
    embed = discord.Embed(title=f"💰 PRIX DU MOMENT — {produit}", description=description,
                           color=0xFFD700, timestamp=datetime.now())
    embed.add_field(name="~~Prix normal~~", value=f"~~{prix_normal}~~", inline=True)
    embed.add_field(name="🔥 Prix promo", value=f"**{prix_promo}**", inline=True)
    embed.add_field(name="⏰ Durée", value=duree, inline=True)
    embed.set_footer(text="Fanatic Ressel • Offre limitée !")
    await ch.send("@everyone", embed=embed)
    await interaction.response.send_message("✅ Promo postée !", ephemeral=True)

@tree.command(name="stock", description="Mettre à jour le stock",
              guild=discord.Object(id=GUILD_ID))
@app_commands.describe(message="Message de stock")
async def stock(interaction: discord.Interaction, message: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Pas autorisé.", ephemeral=True)
        return
    ch = interaction.guild.get_channel(CHANNELS["stock_disponible"])
    embed = discord.Embed(title="📊 STOCK DISPONIBLE", description=message,
                           color=0x7B2FBE, timestamp=datetime.now())
    embed.set_footer(text="Fanatic Ressel • Mis à jour")
    await ch.send(embed=embed)
    await interaction.response.send_message("✅ Stock mis à jour !", ephemeral=True)

class AcceptRulesView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✅ J'accepte les règles", style=discord.ButtonStyle.success,
                        custom_id="accept_rules")
    async def accept_rules(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        role = guild.get_role(ROLE_MEMBRE)
        if role in interaction.user.roles:
            await interaction.response.send_message(
                "✅ T'as déjà accepté les règles !", ephemeral=True)
            return
        if role:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(
                f"✅ Bienvenue sur **Fanatic Ressel** {interaction.user.mention} !\nTu as maintenant accès au serveur. 🔥",
                ephemeral=True)

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 Ouvrir un ticket", style=discord.ButtonStyle.primary,
                        custom_id="open_ticket")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user
        existing = discord.utils.get(guild.channels, name=f"ticket-{user.name.lower()}")
        if existing:
            await interaction.response.send_message(
                f"❌ T'as déjà un ticket ouvert : {existing.mention}", ephemeral=True)
            return
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        admin_role = discord.utils.get(guild.roles, permissions=discord.Permissions(administrator=True))
        if admin_role:
            overwrites[admin_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        channel = await guild.create_text_channel(
            f"ticket-{user.name.lower()}", overwrites=overwrites, topic=f"Ticket de {user}")
        embed = discord.Embed(
            title="🎫 Ticket ouvert",
            description=f"Bonjour {user.mention} !\n\nExplique ta demande ici.\nClique sur **Fermer** quand c'est réglé.",
            color=0x7B2FBE, timestamp=datetime.now())
        embed.set_footer(text="Fanatic Ressel • Support")
        await channel.send(embed=embed, view=CloseTicketView())
        await interaction.response.send_message(f"✅ Ticket créé : {channel.mention}", ephemeral=True)

class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Fermer le ticket", style=discord.ButtonStyle.danger,
                        custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔒 Ticket fermé dans 5 secondes...")
        await asyncio.sleep(5)
        await interaction.channel.delete()

@tree.command(name="setup_ticket", description="Installer le bouton ticket",
              guild=discord.Object(id=GUILD_ID))
async def setup_ticket(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Pas autorisé.", ephemeral=True)
        return
    ch = interaction.guild.get_channel(CHANNELS["ouvrir_ticket"])
    embed = discord.Embed(
        title="🎫 Support — Fanatic Ressel",
        description="Tu as une question ou tu veux passer commande ?\nClique sur le bouton ci-dessous pour ouvrir un ticket privé.",
        color=0x7B2FBE)
    embed.set_footer(text="Fanatic Ressel • Vente - Qualité - Confiance")
    await ch.send(embed=embed, view=TicketView())
    await interaction.response.send_message("✅ Bouton ticket installé !", ephemeral=True)

@tree.command(name="setup_regles", description="Poster les règles du serveur",
              guild=discord.Object(id=GUILD_ID))
async def setup_regles(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Pas autorisé.", ephemeral=True)
        return

    ch = discord.utils.get(interaction.guild.text_channels, name="📌｜𝗥È𝗚𝗟𝗘𝗦")
    if not ch:
        ch = interaction.channel

    embed = discord.Embed(
        title="📋  RÈGLES — FANATIC RESSEL",
        description=(
            "Bienvenue sur **Fanatic Ressel** !\n"
            "*Vente • Qualité • Confiance*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "• Respect absolu — insultes, racisme, harcèlement = **ban immédiat**\n\n"
            "• Pas de spam ni de publicité sans accord du Owner\n\n"
            "• Toute commande se fait **uniquement via ticket**. DM ignorés.\n\n"
            "• Paiement **avant envoi**. Aucune exception.\n\n"
            "• Pas de **charge-back** — ban permanent + poursuites si nécessaire\n\n"
            "• Litiges uniquement **en ticket privé**. Pas en public.\n\n"
            "• Toute tentative d'arnaque = **ban permanent** + signalement\n\n"
            "• Avis dans avis-clients = **réels avec preuves**. Faux avis = ban.\n\n"
            "• Les décisions du staff sont **définitives**\n\n"
            "• Comptes de moins de 30 jours soumis à **vérification**\n\n"
            "• Informations personnelles **confidentielles**\n\n"
            "• **Français uniquement** dans les salons publics\n\n"
            "• Contenu illégal, NSFW ou violent **strictement interdit**\n\n"
            "• Usurpation d'identité du staff = **ban immédiat**\n\n"
            "• Fanatic Ressel ne demande **jamais** tes mots de passe\n\n"
            "• Screenshots de conversations privées **interdits**\n\n"
            "• Stocks limités — **premier arrivé, premier servi**\n\n"
            "• Délais de livraison **indicatifs**\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "✅ En restant sur ce serveur tu acceptes **toutes ces règles**."
        ),
        color=0x7B2FBE
    )
    embed.set_image(url="https://i.imgur.com/89Oceq1.png")
    embed.set_footer(text="Fanatic Ressel • Vente - Qualité - Confiance")

    await ch.send(embed=embed, view=AcceptRulesView())
    await interaction.response.send_message("✅ Règles postées !", ephemeral=True)

bot.run(TOKEN)
