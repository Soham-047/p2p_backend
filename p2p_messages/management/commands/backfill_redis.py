# chatapp/management/commands/backfill_redis.py
from django.core.management.base import BaseCommand
from django.db.models import Q, Max, F
from p2p_messages.models import Message
from p2p_messages.redis_helpers import r, recent_chats_key

class Command(BaseCommand):
    help = 'Backfills Redis recent_chats sorted sets from the existing database.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting to backfill recent chats into Redis...")
        redis_conn = r()

        # Find the last message for each unique conversation pair
        latest_messages = Message.objects.order_by(
            F('sender_id'), F('receiver_id'), '-timestamp'
        ).distinct('sender_id', 'receiver_id')

        count = 0
        with redis_conn.pipeline() as pipe:
            for message in latest_messages:
                user_a = message.sender_id
                user_b = message.receiver_id
                timestamp = int(message.timestamp.timestamp())

                # Add each user to the other's recent chats list
                pipe.zadd(recent_chats_key(user_a), {user_b: timestamp})
                pipe.zadd(recent_chats_key(user_b), {user_a: timestamp})
                count += 1

            pipe.execute()

        self.stdout.write(self.style.SUCCESS(
            f"Successfully backfilled {count} conversations into Redis."
        ))


# run pyhton manage.py backfill_redis to exicute this script, it will backfill the recent chats users in redis.