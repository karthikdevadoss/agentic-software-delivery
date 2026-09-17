package com.example.customer.notification;

import com.example.customer.model.NotificationChannel;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

/**
 * FACTORY PATTERN, composed with STRATEGY: Spring injects every
 * NotificationSender bean present on the classpath (currently 3: EMAIL,
 * SMS, NONE); this factory indexes them by their own declared channel()
 * once at startup and resolves the right strategy for a given
 * NotificationChannel at call time -- callers never construct a sender
 * or branch on the channel enum themselves. Adding a new channel means
 * adding one new @Component; this class does not change.
 */
@Component
public class NotificationSenderFactory {

    private final Map<NotificationChannel, NotificationSender> sendersByChannel;

    public NotificationSenderFactory(List<NotificationSender> senders) {
        this.sendersByChannel = senders.stream()
                .collect(Collectors.toMap(NotificationSender::channel, Function.identity()));
    }

    public NotificationSender getSender(NotificationChannel channel) {
        NotificationSender sender = sendersByChannel.get(channel);
        if (sender == null) {
            throw new IllegalStateException("No NotificationSender registered for channel " + channel);
        }
        return sender;
    }
}
