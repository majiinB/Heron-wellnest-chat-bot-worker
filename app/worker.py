def start_worker():
    """
    Start the Pub/Sub worker to listen for chat messages and process them.

    This worker:
    1. Subscribes to the chat bot Pub/Sub topic
    2. Receives messages with chat events
    3. Processes them using ChatService
    4. Acknowledges successful processing
    """
    import asyncio
    import json
    from google.cloud import pubsub_v1
    from app.config.env_config import env
    from app.service.chat_service import ChatService
    from app.utils.logger_util import LoggerUtil

    # Initialize logger
    logger = LoggerUtil().logger

    try:
        # Configuration
        PROJECT_ID = env.GOOGLE_CLOUD_PROJECT_ID
        SUBSCRIPTION_ID = env.PUBSUB_CHAT_SUBSCRIPTION

        logger.info(f"Starting Pub/Sub worker for project: {PROJECT_ID}, subscription: {SUBSCRIPTION_ID}")

        # Create subscriber client
        try:
            subscriber = pubsub_v1.SubscriberClient()
            subscription_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)
            logger.info(f"Successfully created subscriber client for {subscription_path}")
        except Exception as e:
            logger.error(f"Failed to create Pub/Sub subscriber client: {str(e)}")
            logger.error("Make sure Google Cloud credentials are configured:")
            logger.error("  - Run: gcloud auth application-default login")
            logger.error(f"  - Or set GOOGLE_APPLICATION_CREDENTIALS environment variable")
            return  # Exit gracefully

        async def process_message_async(payload: dict) -> dict:
            """Process a single message asynchronously."""
            from app.config import datasource_config

            try:
                chat_service = ChatService()
                result = await chat_service.process_chat_message(payload)
                return result
            finally:
                # Dispose the engine and reset global to ensure fresh connections next time
                if datasource_config._engine:
                    await datasource_config._engine.dispose()
                    datasource_config._engine = None
                    datasource_config._SessionLocal = None

        def callback(message):
            """
            Callback function for processing Pub/Sub messages.

            Args:
                message: The Pub/Sub message containing chat event data
            """
            try:
                # Parse message data
                message_data = message.data.decode('utf-8')
                logger.info(f"Received Pub/Sub message: {message_data[:200]}...")

                payload = json.loads(message_data)

                # Validate payload has required fields
                if not all(key in payload for key in ['userId', 'sessionId', 'messageId']):
                    logger.error(f"Invalid payload - missing required fields: {payload}")
                    message.nack()  # Reject message
                    return

                # Use asyncio.run() which properly manages event loop lifecycle
                try:
                    result = asyncio.run(process_message_async(payload))

                    if result.get("success"):
                        if result.get("skipped"):
                            logger.info(f"Message processing skipped: {result.get('reason')}")
                        else:
                            logger.info(f"Message processed successfully for session {payload.get('sessionId')}")

                        # Acknowledge the message
                        message.ack()
                    else:
                        logger.error(f"Message processing failed: {result.get('error')}")
                        # Nack to retry (Pub/Sub will redeliver)
                        message.nack()

                except RuntimeError as re:
                    if "Event loop is closed" in str(re):
                        logger.error("Event loop error detected. Retrying...")
                        message.nack()
                    else:
                        raise

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse message JSON: {str(e)}")
                message.nack()  # Reject malformed messages

            except Exception as e:
                logger.error(f"Error processing Pub/Sub message: {str(e)}", exc_info=True)
                message.nack()  # Retry on unexpected errors

        # Configure streaming pull with flow control
        flow_control = pubsub_v1.types.FlowControl(
            max_messages=10,  # Process up to 10 messages concurrently
            max_bytes=10 * 1024 * 1024,  # 10 MB
        )

        # Start streaming pull
        try:
            streaming_pull_future = subscriber.subscribe(
                subscription_path,
                callback=callback,
                flow_control=flow_control
            )
            logger.info(f"✅ Listening for messages on {subscription_path}")
            logger.info(f"Press Ctrl+C to stop the worker")
        except Exception as e:
            logger.error(f"Failed to subscribe to {subscription_path}: {str(e)}")
            logger.error("Make sure the subscription exists:")
            logger.error(f"  - Run: gcloud pubsub subscriptions create {SUBSCRIPTION_ID} --topic=chat-bot-topic --project={PROJECT_ID}")
            return  # Exit gracefully

        # Keep the worker running
        try:
            # Block and wait for messages
            streaming_pull_future.result()
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down worker...")
            streaming_pull_future.cancel()
            streaming_pull_future.result()  # Wait for cancellation to complete
            logger.info("Worker stopped")
        except Exception as e:
            logger.error(f"Worker error: {str(e)}", exc_info=True)
            streaming_pull_future.cancel()

    except Exception as e:
        logger.error(f"Fatal error starting Pub/Sub worker: {str(e)}", exc_info=True)
        logger.error("Worker will not start. Please check:")
        logger.error("  1. Google Cloud credentials are configured")
        logger.error("  2. Pub/Sub subscription exists")
        logger.error("  3. Database connection is working")
