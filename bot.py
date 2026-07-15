import os
import threading
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from flask import Flask

load_dotenv()
TOKEN = os.environ.get("DISCORD_BOT_TOKEN")

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
                f"⚠ Role '{VERIFIED_ROLE_NAME}' tidak ditemukan. Hubungi admin.",
                ephemeral=True
            )
            return

        if role in member.roles:
            await interaction.response.send_message(
                "✅ Kamu sudah terverifikasi sebelumnya!",
                ephemeral=True
            )
            return

        try:
            await member.add_roles(role)
            await interaction.response.send_message(
                "🎉 Verifikasi berhasil! Selamat datang di server 3DRBXMT.",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "⚠ Bot tidak punya izin untuk memberikan role ini. Hubungi admin.",
                ephemeral=True
            )


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


@bot.tree.command(name="setup_verify", description="Kirim pesan verifikasi dengan tombol (admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_verify(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🔒 Verifikasi Member",
        description=(
            "Selamat datang di **3DRBXMT Community**!\n\n"
            "Klik tombol di bawah untuk verifikasi dan mendapatkan akses penuh ke server."
        ),
        color=0x00D4FF
    )
    embed.set_footer(text="3DRBXMT · Roblox 3D Model Tools")

    await interaction.channel.send(embed=embed, view=VerifyView())
    await interaction.response.send_message("✓ Pesan verifikasi berhasil dikirim!", ephemeral=True)


@setup_verify.error
async def setup_verify_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "⚠ Kamu tidak punya izin untuk menjalankan command ini.",
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
            placeholder="Pilih role kamu (bisa lebih dari satu)...",
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
            msg_parts.append(f"✅ Ditambahkan: {', '.join(added)}")
        if removed:
            msg_parts.append(f"➖ Dihapus: {', '.join(removed)}")
        if missing:
            msg_parts.append(f"⚠ Role tidak ditemukan di server: {', '.join(missing)}")
        if not msg_parts:
            msg_parts.append("Tidak ada perubahan.")

        await interaction.response.send_message("\n".join(msg_parts), ephemeral=True)


class RoleSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(RoleSelect())


@bot.tree.command(name="setup_roles", description="Kirim menu pemilihan role (admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_roles(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🏷️ Pilih Role Kamu",
        description=(
            "Pilih role yang sesuai dengan software, skill, atau bahasa kamu.\n"
            "Bisa pilih lebih dari satu sekaligus lewat dropdown di bawah.\n\n"
            "**Software/Skill:** Prisma 3D, Nomad Sculpt, 3D Modeler, 2D Artist\n"
            "**Bahasa:** Indonesian, English, Other Languages\n\n"
            "⚠ Role **Content Creator** dan **Moderator** tidak tersedia di sini — hubungi Dev/Admin langsung jika ingin role tersebut."
        ),
        color=0x00D4FF
    )
    embed.set_footer(text="3DRBXMT · Roblox 3D Model Tools")

    await interaction.channel.send(embed=embed, view=RoleSelectView())
    await interaction.response.send_message("✓ Menu role berhasil dikirim!", ephemeral=True)


@setup_roles.error
async def setup_roles_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "⚠ Kamu tidak punya izin untuk menjalankan command ini.",
            ephemeral=True
        )


if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    bot.run(TOKEN)
