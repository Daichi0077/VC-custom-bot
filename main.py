import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Modal, TextInput
import os
import asyncio

# --- 設定項目 ---
# !!! 重要: Botトークンは公開しないでください。環境変数などに設定することを強く推奨します。!!!
# TOKEN = os.getenv("DISCORD_BOT_TOKEN") # 環境変数からトークンを読み込むことを強く推奨
TOKEN = os.getenv("DISCORD_BOT_TOKEN") # 環境変数からトークンを読み込む
if TOKEN is None or TOKEN == "YOUR_BOT_TOKEN_HERE": # 環境変数が設定されていない、またはデフォルト値のままの場合
    print("エラー: ボットトークンが設定されていません。環境変数 'DISCORD_BOT_TOKEN' を設定してください。")
    print("または、コード内の 'TOKEN = \"...\"' の部分に実際のトークンを入力してください（非推奨）。")
    exit(1)
ONLINE_BOT_CHANNEL_ID = 1381654525986738180
STATUS_CHANNEL_ID = 1375779142905233508  # ← VC通知を出すテキストチャンネルID
OWNER_ID = 1220256562371756042  # ← 管理者のユーザーID（右クリック→IDコピー）

# !!! 重要: テスト用のギルドIDを設定してください !!!
TEST_GUILD_ID = 1289587808956186734 # <-- ここにあなたのテストサーバーのIDを入れてください

# -----------------

intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.members = True # メンバー情報を取得するために必要

bot = commands.Bot(command_prefix="!", intents=intents)

# Discordの内部ルーティングに基づいたパス生成のヘルパー関数
def build_channel_voice_status_route(channel_id: int):
    return f"/channels/{channel_id}/voice-status"

# ---------- モーダル ----------
class VCStatusModal(Modal, title="VCステータスを設定"):
    status_input = TextInput(label="ステータスを入力", placeholder="例：雑談中、作業中 など", max_length=100)

    def __init__(self, vc_channel):
        super().__init__()
        self.vc_channel = vc_channel

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            # 非公式APIによるVCステータス更新を試みる
            await bot.http.request(
                discord.http.Route("PUT", build_channel_voice_status_route(self.vc_channel.id)),
                json={"status": self.status_input.value}
            )
            await interaction.followup.send(
                f"✅ VCの**直接**ステータスを「{self.status_input.value}」に設定しました。",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ 権限不足のためVCステータスの直接変更に失敗しました。Botに適切な権限があるか確認してください。",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ VCステータスの直接変更中にエラーが発生しました: {e}\n(非公式APIのため、API変更の可能性があります)",
                ephemeral=True
            )
            print(f"非公式API呼び出しエラー: {e}")


# ---------- VCステータス変更ボタンビュー ----------
class SetVCStatusView(View):
    def __init__(self, vc_channel):
        super().__init__(timeout=60) # ボタンの有効期限を60秒に設定
        self.vc_channel = vc_channel

    @discord.ui.button(label="VCステータスを設定", style=discord.ButtonStyle.primary, custom_id="set_vc_status_button")
    async def set_status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # ボタンを押したユーザーが、コマンド実行時に指定されたVCに実際に接続しているか確認
        if interaction.user.voice and interaction.user.voice.channel and interaction.user.voice.channel.id == self.vc_channel.id:
            await interaction.response.send_modal(VCStatusModal(self.vc_channel))
        else:
            await interaction.response.send_message("❌ このボタンはあなたが現在接続しているVCのステータスを変更するためのものです。", ephemeral=True)
            await interaction.message.delete() # 役割を終えたボタンメッセージを削除


# ---------- スラッシュコマンド定義 ----------

# Botのシャットダウンコマンド
@bot.tree.command(name="shutdown", description="Botをオフラインにします（管理者専用）", guild=discord.Object(id=TEST_GUILD_ID))
async def shutdown(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("⚠️ このコマンドを使用する権限がありません。", ephemeral=True)
        return
    await interaction.response.send_message("🛑 Botをシャットダウンします...", ephemeral=True)
    await bot.close()

# VCステータス変更ボタンを表示するコマンド
@bot.tree.command(name="setvcstatus", description="現在のVCのステータス変更ボタンを表示します", guild=discord.Object(id=TEST_GUILD_ID))
async def setvcstatus(interaction: discord.Interaction):
    # コマンドを実行したユーザーがVCに接続しているか確認
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message("❌ まずボイスチャンネルに接続してください。", ephemeral=True)
        return

    vc_channel = interaction.user.voice.channel
    view = SetVCStatusView(vc_channel)
    await interaction.response.send_message(
        f"✅ VC **{vc_channel.name}** のステータスを設定します。下のボタンを押してください👇",
        view=view,
        ephemeral=True # コマンド実行者のみに見えるようにする
    )

# ---------- Bot起動時 ----------
@bot.event
async def on_ready():
    print(f"ログインしました: {bot.user.name} ({bot.user.id})")

    # スラッシュコマンドの同期
    if TEST_GUILD_ID:
        try:
            guild_obj = discord.Object(id=TEST_GUILD_ID)
            await bot.tree.sync(guild=guild_obj)
            print(f"✅ スラッシュコマンドをギルドID {TEST_GUILD_ID} に同期しました。")
        except discord.DiscordException as e:
            print(f"エラー: ギルドID {TEST_GUILD_ID} へのコマンド同期に失敗しました: {e}")
    else:
        try:
            await bot.tree.sync()
            print("✅ グローバルスラッシュコマンドを同期しました。（反映に時間がかかる場合があります）")
        except discord.DiscordException as e:
            print(f"エラー: グローバルコマンド同期に失敗しました: {e}")

    # 永続Viewは今回は使用しないため削除

    channel = bot.get_channel(ONLINE_BOT_CHANNEL_ID)
    if channel:
        try:
            await channel.send("✅ Botがオンラインになりました！（コマンド同期済み）")
        except discord.Forbidden:
            print(f"エラー: テキストチャンネル {STATUS_CHANNEL_ID} にメッセージを送信する権限がありません。")
        except Exception as e:
            print(f"エラー: テキストチャンネルへの起動通知送信中に問題が発生しました: {e}")


# ---------- VC参加時イベント ----------
@bot.event
async def on_voice_state_update(member, before, after):
    # Bot自身のボイスステータス更新は無視
    if member.id == bot.user.id:
        return

    # ユーザーがVCに参加したとき (VCからVCへの移動も含む)
    if after.channel is not None and (before.channel is None or before.channel.id != after.channel.id):
        # 鯖主（OWNER_ID）が参加した場合の通知
        if member.id == OWNER_ID:
            text_channel = bot.get_channel(STATUS_CHANNEL_ID)
            if text_channel:
                 # VCへのリンクを作成
                vc_link = f"discord://discord.com/channels/{after.channel.guild.id}/{after.channel.id}"
                
                # テキストコンテンツ (ロールメンション、VCチャンネル名、そして「クリックして参加」リンク)
                # ここでVCチャンネル名とクリックできる参加リンクを両方含める
                message_content = (
                    f"<@&1325425584666316921> <#{after.channel.id}>\n"
                    f"[クリックして参加]({vc_link})"
                )
                
                # 埋め込みメッセージを作成
                embed = discord.Embed(
                    title="👑 鯖主VC通知",
                    description=f"{member.mention} が **{after.channel.name}** に参加しました！",
                    color=discord.Color.gold()
                )
                # embed内の「VCに参加しよう」フィールドは、message_contentでカバーするため削除
                embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
                embed.set_footer(text="お疲れ様です")

                try:
                    # テキストコンテンツと埋め込みメッセージを同時に送信
                    await text_channel.send(content=message_content, embed=embed, allowed_mentions=discord.AllowedMentions(roles=True))
                except discord.Forbidden:
                    print(f"エラー: テキストチャンネル {STATUS_CHANNEL_ID} に管理者VC参加通知を送信する権限がありません。")
                except Exception as e:
                    print(f"エラー: 管理者VC参加通知の送信中に問題が発生しました: {e}")

        # VC接続時にモーダルを出す処理は削除しました

# ---------- Bot起動 ----------
try:
    bot.run(TOKEN)
except discord.LoginFailure:
    print("エラー: ボットトークンが無効です。Discord Developersサイトでトークンを確認してください。")
except Exception as e:
    print(f"ボットの起動中に予期せぬエラーが発生しました: {e}")
