import time
import logging
from Config import Config
from pyrogram import Client, filters, enums
from sql_helpers import forceSubscribe_sql as sql
from pyrogram.types import ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors.exceptions.bad_request_400 import UserNotParticipant, UsernameNotOccupied, ChatAdminRequired, \
    PeerIdInvalid

logging.basicConfig(level=logging.INFO)

static_data_filter = filters.create(lambda _, __, query: query.data == "onUnMuteRequest")


@Client.on_callback_query(static_data_filter)
async def _onUnMuteRequest(client, cb):
    user_id = cb.from_user.id
    chat_id = cb.message.chat.id
    chat_db = sql.fs_settings(chat_id)
    if chat_db:
        channel = chat_db.channel
        chat_member = await client.get_chat_member(chat_id, user_id)
        if chat_member.restricted_by:
            if chat_member.restricted_by.id == (await client.get_me()).id:
                try:
                    await client.get_chat_member(channel, user_id)
                    await client.unban_chat_member(chat_id, user_id)
                    if cb.message.reply_to_message.from_user.id == user_id:
                        await cb.message.delete()
                except UserNotParticipant:
                    await client.answer_callback_query(cb.id, text="הצטרף לערוץ למטה ואז לחץ על הכפתור",
                                                       show_alert=True)
            else:
                await client.answer_callback_query(cb.id, text="❗ You are muted by admins for other reasons.",
                                                   show_alert=True)
        else:
            if not (await client.get_chat_member(chat_id, (await client.get_me()).id)).status == enums.ChatMemberStatus.ADMINISTRATOR:
                await client.send_message(chat_id,
                                          f"❗ **{cb.from_user.mention} is trying to UnMute himself but i can't unmute him because i am not an admin in this chat add me as admin again.**\n__#Leaving this chat...__")
                await client.leave_chat(chat_id)
            else:
                await client.answer_callback_query(cb.id,
                                                   text="❗ אל תלחץ אם אתה לא מוגבל!",
                                                   show_alert=True)


@Client.on_message((filters.text | filters.media) & ~filters.private, group=1)
async def _check_member(client, message):
    global sent_message
    chat_id = message.chat.id
    chat_db = sql.fs_settings(chat_id)
    # chat_db = True
    if chat_db:
        user_id = message.from_user.id
        if not (await client.get_chat_member(chat_id, user_id)).status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER] and not user_id in Config.SUDO_USERS:
            channel = chat_db.channel
            if channel.startswith("-"):
                channel_url = await client.export_chat_invite_link(int(channel))
            else:
                channel_url = f"https://t.me/{channel}"
            try:
                await client.get_chat_member(channel, user_id)
            except UserNotParticipant:
                try:
                    sent_message = await message.reply_text(
                        " {} ,אתה לא חבר בערוץ המופיע למטה, הצטרף לערןץ בכפתור למטה ואז לחץ על שחרר אותי".format(
                            message.from_user.mention, channel, channel),

                        disable_web_page_preview=True,
                        reply_markup=InlineKeyboardMarkup(
                            [
                                [
                                    InlineKeyboardButton("לחץ להצטרפות לערוץ", url=channel_url)
                                ],
                                [
                                    InlineKeyboardButton("שחרר אותי", callback_data="onUnMuteRequest")
                                ]
                            ]
                        )
                    )
                    await client.restrict_chat_member(chat_id, user_id, ChatPermissions(can_send_messages=False))
                except ChatAdminRequired:
                    await sent_message.edit(
                        "❗ **I am not an admin here.**\n__Make me admin with ban user permission and add me again.\n#Leaving this chat...__")
                    await client.leave_chat(chat_id)
            except ChatAdminRequired:
                await client.send_message(chat_id,
                                          text=f"❗ **I am not an admin in [channel]({channel_url})**\n__Make me admin in the channel and add me again.\n#Leaving this chat...__")
                await client.leave_chat(chat_id)


@Client.on_message(filters.command(["forcesubscribe", "fsub"]) & ~filters.private)
async def config(client, message):
    user = await client.get_chat_member(message.chat.id, message.from_user.id)
    if user.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER] or user.user.id in Config.SUDO_USERS:
        chat_id = message.chat.id
        if len(message.command) > 1:
            input_str = message.command[1].replace("@", "")
            if input_str.lower() in ("off", "no", "disable"):
                sql.disapprove(chat_id)
                await message.reply_text("❌ **Force Subscribe is Disabled Successfully.**")
            elif input_str.lower() == 'clear':
                sent_message = await message.reply_text('**Unmuting all members who are muted by me...**')
                try:
                    for chat_member in (await client.get_chat_members(message.chat.id, filter="restricted")):
                        if chat_member.restricted_by.id == (await client.get_me()).id:
                            await client.unban_chat_member(chat_id, chat_member.user.id)
                            time.sleep(1)
                    await sent_message.edit('✅ **UnMuted all members who are muted by me.**')
                except ChatAdminRequired:
                    await sent_message.edit(
                        '❗ **I am not an admin in this chat.**\n__I can\'t unmute members because I am not an admin in this chat. Make me an admin with ban user permission.__')
            else:
                try:
                    await client.get_chat_member(input_str, "me")
                    sql.add_channel(chat_id, input_str)
                    if input_str.startswith("-"):
                        channel_url = await client.export_chat_invite_link(int(input_str))
                    else:
                        channel_url = f"https://t.me/{input_str}"
                    await message.reply_text(
                        f"✅ **Force Subscribe is Enabled**\n__Force Subscribe is enabled, all the group members have to subscribe to this channel in order to send messages in this group.__",
                        disable_web_page_preview=True)
                except UserNotParticipant:
                    await message.reply_text(
                        f"❗ **Not an Admin in the Channel**\n__I am not an admin in the channel. Add me as an admin in order to enable ForceSubscribe.__",
                        disable_web_page_preview=True)
                except (UsernameNotOccupied, PeerIdInvalid):
                    await message.reply_text(f"❗ **Invalid Channel Username/ID.**")
                except Exception as err:
                    print(err)
                    await message.reply_text(f"❗ **ERROR:** ```{err}```")
        else:
            if sql.fs_settings(chat_id):
                my_channel = sql.fs_settings(chat_id).channel
                if my_channel.startswith("-"):
                    channel_url = await client.export_chat_invite_link(int(my_channel))
                else:
                    channel_url = f"https://t.me/{my_channel}"
                await message.reply_text(
                    f"✅ **Force Subscribe is enabled in this chat.**\n__For this Channel__",
                    disable_web_page_preview=True)
            else:
                await message.reply_text("❌ **Force Subscribe is disabled in this chat.**")
    else:
        await message.reply_text("❗ **Group Creator Required**\n__You have to be the group creator to do that.__")
