from google.cloud import videointelligence_v1 as videointelligence
from google.cloud import storage
import os
import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

# Set up Google Cloud credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'secret.json'
video_client = videointelligence.VideoIntelligenceServiceClient()

# Set up Telegram bot token and bucket details
TELEGRAM_TOKEN = 'BOT_TOKEN'
BUCKET_NAME = 'videos_for_label_detection'

# Create a Telegram bot
bot = telegram.Bot(token=TELEGRAM_TOKEN)

# Create a client for Google Cloud Storage
storage_client = storage.Client()

def detect_labels_on_video(gs_uri):
    features = [videointelligence.Feature.LABEL_DETECTION]

    operation = video_client.annotate_video(request={"input_uri": gs_uri, "features": features})
    print('\nProcessing video for label annotations:')

    result = operation.result(timeout=120)
    annotation_results = result.annotation_results

    segment_labels = annotation_results[0].segment_label_annotations

    labels = []
    for i, segment_label in enumerate(segment_labels):
        label_description = segment_label.entity.description
        labels.append(label_description)

    return labels


def process_video(update, context):
    # Check if the message contains a video
    if not update.message.video:
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="Please send a video file.")
        return

    # Download the video file
    file_id = update.message.video.file_id
    new_file = context.bot.get_file(file_id)
    file_path = os.path.join(os.path.dirname(__file__), 'tmp', f'{file_id}.mp4')
    new_file.download(file_path)

    # Upload the video file to Google Cloud Storage
    bucket = storage_client.bucket(BUCKET_NAME)
    blob_name = f'videos/{file_id}.mp4'
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(file_path)

    # Generate a public URL for the uploaded video
    gs_uri = f'gs://{BUCKET_NAME}/{blob_name}'

    # Detect labels on the video
    labels = detect_labels_on_video(gs_uri)

    # Send the labels as a reply
    reply_text = "Detected labels:\n\n"
    reply_text += "\n".join(labels)
    context.bot.send_message(chat_id=update.effective_chat.id, text=reply_text)

    # Clean up the downloaded video file
    os.remove(file_path)


def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Welcome to the Video Label Detection Bot!\n\n"
                                  "Send me a video file to detect labels.")


def main():
    # Create an Updater for the bot
    updater = Updater(TELEGRAM_TOKEN, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # Register a command handler to start the bot
    dp.add_handler(CommandHandler("start", start))

    # Register a message handler for videos
    dp.add_handler(MessageHandler(Filters.video, process_video))

    # Start the bot
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
