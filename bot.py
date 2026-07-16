import os
import threading
import requests
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from flask import Flask

load_dotenv()
TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")


def get_web_maintenance_state():
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/app_state",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}"
            },
            params={"key": "eq.maintenance_mode", "select": "value"},
            timeout=5
        )
        data = r.json()
        if data and len(data) > 0:
            return data[0].get("value", False)
        return False
    except Exception:
        return None  # None = error/unknown


def set_web_maintenance_state(active):
    try:
        requests.patch(
            f"{SUPABASE_URL}/rest/v1/app_state",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json"
            },
            params={"key": "eq.maintenance_mode"},
            json={"value": active},
            timeout=5
        )
        return True
    except Exception:
        return False

# ── FLASK KEEP-ALIVE SERVER ──────────────────────────────
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

VERIFIED_ROLE_NAME = "Member"  # Ganti sesuai nama role yang mau dikasih setelah verify


class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Tombol tidak expire

    @discord.ui.button(label="✅ Verify", style=discord.ButtonStyle.success, custom_id="verify_button")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = interaction.user

        role = discord.utils.get(guild.roles, name=VERIFIED_ROLE_NAME)
        if role is None:
            await interaction.response.send_message(
                f"⚠ Role '{VERIFIED_ROLE_NAME}' not found. Contact an admin.",
                ephemeral=True
            )
            return

        if role in member.roles:
            await interaction.response.send_message(
                "✅ You are already verified!",
                ephemeral=True
            )
            return

        try:
            await member.add_roles(role)
            await interaction.response.send_message(
                "🎉 Verification successful! Welcome to the 3DRBXMT server.",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "⚠ The bot doesn't have permission to assign this role. Contact an admin.",
                ephemeral=True
            )


ALLOWED_YOUTUBE_CHANNEL = "youtube-upload"
YOUTUBE_PATTERNS = ["youtube.com", "youtu.be"]


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.name != ALLOWED_YOUTUBE_CHANNEL:
        content_lower = message.content.lower()
        if any(pattern in content_lower for pattern in YOUTUBE_PATTERNS):
            try:
                await message.delete()
                warning = await message.channel.send(
                    f"{message.author.mention} ⚠ YouTube links are only allowed in <#{discord.utils.get(message.guild.text_channels, name=ALLOWED_YOUTUBE_CHANNEL).id if discord.utils.get(message.guild.text_channels, name=ALLOWED_YOUTUBE_CHANNEL) else ALLOWED_YOUTUBE_CHANNEL}>."
                )
                await warning.delete(delay=8)
            except discord.Forbidden:
                pass
            return

    await bot.process_commands(message)


WELCOME_CHANNEL_NAME = "welcome"


@bot.event
async def on_member_join(member):
    channel = discord.utils.get(member.guild.text_channels, name=WELCOME_CHANNEL_NAME)
    if channel is None:
        return

    verify_channel = discord.utils.get(member.guild.text_channels, name="verify")
    verify_mention = f"<#{verify_channel.id}>" if verify_channel else "#verify"

    embed = discord.Embed(
        title="🎉 Welcome to 3RBX-MGT",
        description=(
            f"Hey {member.mention}!\n\n"
            f"Welcome to **3D ROBLOX MODEL MOBILE GLOBAL TOOLS** Official.\n\n"
            f"Don't forget to read the **RULES** in {verify_mention} channel and get verified to unlock full access!"
        ),
        color=0x00D4FF
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"Member #{member.guild.member_count} · 3DRBXMT")

    try:
        await channel.send(embed=embed)
    except discord.Forbidden:
        pass


@bot.event
async def on_ready():
    print(f"✓ Bot login sebagai {bot.user}")
    bot.add_view(VerifyView())  # Register persistent view supaya tombol tetap jalan setelah restart
    bot.add_view(RoleSelectView())  # Register persistent view untuk role select menu
    try:
        synced = await bot.tree.sync()
        print(f"✓ {len(synced)} slash command(s) synced")
    except Exception as e:
        print(f"✗ Gagal sync commands: {e}")


@bot.tree.command(name="setup_verify", description="Send a verification message with a button (admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_verify(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🔒 Member Verification",
        description=(
            "Welcome to **3DRBXMT Community**!\n\n"
            "Click the button below to verify and get full access to the server."
        ),
        color=0x00D4FF
    )
    embed.set_footer(text="3DRBXMT · Roblox 3D Model Tools")

    await interaction.channel.send(embed=embed, view=VerifyView())
    await interaction.response.send_message("✓ Verification message sent successfully!", ephemeral=True)


@setup_verify.error
async def setup_verify_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "⚠ You don't have permission to run this command.",
            ephemeral=True
        )


ROLE_OPTIONS = [
    ("Prisma 3D", "🎨"),
    ("Nomad Sculpt", "🗿"),
    ("3D Modeler", "📦"),
    ("2D Artist", "🖌️"),
    ("Indonesian", "🇮🇩"),
    ("English", "🇬🇧"),
    ("Other Languages", "🌐"),
]


class RoleSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=name, emoji=emoji, value=name)
            for name, emoji in ROLE_OPTIONS
        ]
        super().__init__(
            placeholder="Choose your roles (you can select more than one)...",
            min_values=0,
            max_values=len(options),
            options=options,
            custom_id="role_select_menu"
        )

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user
        selected = set(self.values)
        all_role_names = {name for name, _ in ROLE_OPTIONS}

        added, removed, missing = [], [], []

        for role_name in all_role_names:
            role = discord.utils.get(guild.roles, name=role_name)
            if role is None:
                missing.append(role_name)
                continue
            has_role = role in member.roles
            wants_role = role_name in selected

            if wants_role and not has_role:
                await member.add_roles(role)
                added.append(role_name)
            elif not wants_role and has_role:
                await member.remove_roles(role)
                removed.append(role_name)

        msg_parts = []
        if added:
            msg_parts.append(f"✅ Added: {', '.join(added)}")
        if removed:
            msg_parts.append(f"➖ Removed: {', '.join(removed)}")
        if missing:
            msg_parts.append(f"⚠ Role(s) not found on server: {', '.join(missing)}")
        if not msg_parts:
            msg_parts.append("No changes made.")

        await interaction.response.send_message("\n".join(msg_parts), ephemeral=True)


class RoleSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(RoleSelect())


@bot.tree.command(name="setup_roles", description="Send the role selection menu (admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_roles(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🏷️ Choose Your Roles",
        description=(
            "Select the roles that match your software, skill, or language.\n"
            "You can select more than one at once from the dropdown below.\n\n"
            "**Software/Skill:** Prisma 3D, Nomad Sculpt, 3D Modeler, 2D Artist\n"
            "**Language:** Indonesian, English, Other Languages\n\n"
            "⚠ The **Content Creator** and **Moderator** roles are not available here — contact the Dev/Admin directly if you'd like those roles."
        ),
        color=0x00D4FF
    )
    embed.set_footer(text="3DRBXMT · Roblox 3D Model Tools")

    await interaction.channel.send(embed=embed, view=RoleSelectView())
    await interaction.response.send_message("✓ Role menu sent successfully!", ephemeral=True)


@setup_roles.error
async def setup_roles_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "⚠ You don't have permission to run this command.",
            ephemeral=True
        )


@bot.tree.command(name="checkproto", description="Check if Protogen Security is online and working")
async def checkproto(interaction: discord.Interaction):
    await interaction.response.send_message(
        "proto security is here, just watching the community and spying on the DEV =w="
    )


ANNOUNCEMENT_CHANNEL_NAME = "announcement"


@bot.tree.command(name="announce", description="Send an announcement to the announcement channel (admin only)")
@app_commands.describe(title="Title of the announcement", message="The announcement content")
@app_commands.checks.has_permissions(administrator=True)
async def announce(interaction: discord.Interaction, title: str, message: str):
    channel = discord.utils.get(interaction.guild.text_channels, name=ANNOUNCEMENT_CHANNEL_NAME)
    if channel is None:
        await interaction.response.send_message(
            f"⚠ Channel #{ANNOUNCEMENT_CHANNEL_NAME} not found.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title=f"📢 {title}",
        description=message,
        color=0x00D4FF
    )
    embed.set_footer(text="3DRBX-MGT · Official Announcement")

    try:
        await channel.send(content="@here", embed=embed)
        await interaction.response.send_message(
            f"✓ Announcement sent to #{ANNOUNCEMENT_CHANNEL_NAME}!",
            ephemeral=True
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            "⚠ The bot doesn't have permission to send messages in that channel.",
            ephemeral=True
        )


@announce.error
async def announce_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "⚠ You don't have permission to run this command.",
            ephemeral=True
        )


class StatusToggleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="🔧 Set to Maintenance", style=discord.ButtonStyle.danger)
    async def set_maintenance(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "⚠ Only admins can change the website status.",
                ephemeral=True
            )
            return
        await interaction.response.defer()
        success = set_web_maintenance_state(True)
        if success:
            await interaction.edit_original_response(
                content="🔧 Website status set to **MAINTENANCE**.",
                embed=None, view=None
            )
        else:
            await interaction.edit_original_response(
                content="✗ Failed to update status.", embed=None, view=None
            )

    @discord.ui.button(label="✅ Set to Live", style=discord.ButtonStyle.success)
    async def set_live(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "⚠ Only admins can change the website status.",
                ephemeral=True
            )
            return
        await interaction.response.defer()
        success = set_web_maintenance_state(False)
        if success:
            await interaction.edit_original_response(
                content="✅ Website status set to **LIVE**.",
                embed=None, view=None
            )
        else:
            await interaction.edit_original_response(
                content="✗ Failed to update status.", embed=None, view=None
            )


@bot.tree.command(name="statusweb", description="Check 3DRBXMT website status (maintenance or live)")
async def statusweb(interaction: discord.Interaction):
    state = get_web_maintenance_state()

    if state is None:
        await interaction.response.send_message("⚠ Unable to fetch website status right now.", ephemeral=True)
        return

    status_text = "🔧 **MAINTENANCE**" if state else "✅ **LIVE**"
    embed = discord.Embed(
        title="🌐 3DRBXMT Website Status",
        description=f"Current status: {status_text}",
        color=0xFF3355 if state else 0x00D4FF
    )
    embed.set_footer(text="getrbx3d.qzz.io")

    await interaction.response.send_message(embed=embed, view=StatusToggleView())


# ── MODERATION COMMANDS ───────────────────────────────────

@bot.tree.command(name="kick", description="Kick a member from the server (mod only)")
@app_commands.describe(member="Member to kick", reason="Reason for kicking")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    try:
        await member.kick(reason=reason)
        await interaction.response.send_message(f"👢 {member.mention} has been kicked. Reason: {reason}")
    except discord.Forbidden:
        await interaction.response.send_message("⚠ I don't have permission to kick this member.", ephemeral=True)


@kick.error
async def kick_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("⚠ You don't have permission to run this command.", ephemeral=True)


@bot.tree.command(name="ban", description="Ban a member from the server (mod only)")
@app_commands.describe(member="Member to ban", reason="Reason for banning")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    try:
        await member.ban(reason=reason)
        await interaction.response.send_message(f"🔨 {member.mention} has been banned. Reason: {reason}")
    except discord.Forbidden:
        await interaction.response.send_message("⚠ I don't have permission to ban this member.", ephemeral=True)


@ban.error
async def ban_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("⚠ You don't have permission to run this command.", ephemeral=True)


@bot.tree.command(name="timeout", description="Timeout (mute) a member for a duration (mod only)")
@app_commands.describe(member="Member to timeout", minutes="Duration in minutes", reason="Reason for timeout")
@app_commands.checks.has_permissions(moderate_members=True)
async def timeout(interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "No reason provided"):
    import datetime
    try:
        duration = datetime.timedelta(minutes=minutes)
        await member.timeout(duration, reason=reason)
        await interaction.response.send_message(f"🔇 {member.mention} has been timed out for {minutes} minute(s). Reason: {reason}")
    except discord.Forbidden:
        await interaction.response.send_message("⚠ I don't have permission to timeout this member.", ephemeral=True)


@timeout.error
async def timeout_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("⚠ You don't have permission to run this command.", ephemeral=True)


@bot.tree.command(name="clear", description="Delete a number of recent messages (mod only)")
@app_commands.describe(amount="Number of messages to delete (max 100)")
@app_commands.checks.has_permissions(manage_messages=True)
async def clear(interaction: discord.Interaction, amount: int):
    if amount < 1 or amount > 100:
        await interaction.response.send_message("⚠ Amount must be between 1 and 100.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"🧹 Deleted {len(deleted)} message(s).", ephemeral=True)


@clear.error
async def clear_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("⚠ You don't have permission to run this command.", ephemeral=True)


warnings_store = {}


@bot.tree.command(name="warn", description="Warn a member (mod only)")
@app_commands.describe(member="Member to warn", reason="Reason for warning")
@app_commands.checks.has_permissions(moderate_members=True)
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str):
    user_id = str(member.id)
    warnings_store.setdefault(user_id, []).append(reason)
    count = len(warnings_store[user_id])
    await interaction.response.send_message(
        f"⚠ {member.mention} has been warned. Reason: {reason}\nTotal warnings: {count}"
    )


@warn.error
async def warn_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("⚠ You don't have permission to run this command.", ephemeral=True)


@bot.tree.command(name="warnings", description="Check a member's warning history (mod only)")
@app_commands.describe(member="Member to check")
@app_commands.checks.has_permissions(moderate_members=True)
async def warnings_cmd(interaction: discord.Interaction, member: discord.Member):
    user_id = str(member.id)
    reasons = warnings_store.get(user_id, [])
    if not reasons:
        await interaction.response.send_message(f"{member.mention} has no warnings.", ephemeral=True)
        return
    formatted = "\n".join(f"{i+1}. {r}" for i, r in enumerate(reasons))
    await interaction.response.send_message(
        f"⚠ Warning history for {member.mention} ({len(reasons)} total):\n{formatted}",
        ephemeral=True
    )


@warnings_cmd.error
async def warnings_cmd_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("⚠ You don't have permission to run this command.", ephemeral=True)


# ── SERVER STATS & BOT INFO ────────────────────────────────

@bot.tree.command(name="serverstats", description="Show server statistics")
async def serverstats(interaction: discord.Interaction):
    guild = interaction.guild
    total_members = guild.member_count
    online_members = sum(1 for m in guild.members if m.status != discord.Status.offline)
    text_channels = len(guild.text_channels)
    voice_channels = len(guild.voice_channels)
    role_count = len(guild.roles)

    embed = discord.Embed(title=f"📊 {guild.name} Stats", color=0x00D4FF)
    embed.add_field(name="Total Members", value=str(total_members), inline=True)
    embed.add_field(name="Online Members", value=str(online_members), inline=True)
    embed.add_field(name="Text Channels", value=str(text_channels), inline=True)
    embed.add_field(name="Voice Channels", value=str(voice_channels), inline=True)
    embed.add_field(name="Roles", value=str(role_count), inline=True)
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="botinfo", description="Show bot information (ping, uptime, etc)")
async def botinfo(interaction: discord.Interaction):
    latency_ms = round(bot.latency * 1000)
    embed = discord.Embed(title="🤖 Protogen Security Info", color=0x00D4FF)
    embed.add_field(name="Ping", value=f"{latency_ms}ms", inline=True)
    embed.add_field(name="Servers", value=str(len(bot.guilds)), inline=True)
    embed.set_footer(text="3DRBX-MGT · Protogen Security")

    await interaction.response.send_message(embed=embed)


PROTECTED_ROLES = ["Dev", "Moderator", "BOT", "Protogen Security"]


@bot.tree.command(name="revokerole", description="Revoke a role from a member as punishment (mod only)")
@app_commands.describe(member="Member to revoke role from", role="Role to revoke", reason="Reason for revoking")
@app_commands.checks.has_permissions(manage_roles=True)
async def revokerole(interaction: discord.Interaction, member: discord.Member, role: discord.Role, reason: str = "No reason provided"):
    if role.name in PROTECTED_ROLES:
        await interaction.response.send_message(
            f"⛔ The role **{role.name}** is protected and cannot be revoked through this command.",
            ephemeral=True
        )
        return

    if role not in member.roles:
        await interaction.response.send_message(
            f"⚠ {member.mention} doesn't have the role **{role.name}**.",
            ephemeral=True
        )
        return

    try:
        await member.remove_roles(role, reason=reason)
        await interaction.response.send_message(
            f"🚫 Role **{role.name}** has been revoked from {member.mention}.\nReason: {reason}"
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            "⚠ I don't have permission to remove this role (check role hierarchy).",
            ephemeral=True
        )


@revokerole.error
async def revokerole_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("⚠ You don't have permission to run this command.", ephemeral=True)


if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    bot.run(TOKEN)
