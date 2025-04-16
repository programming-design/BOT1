# General responses
GENERAL = {
    "error": "حدث خطأ: {error}",
    "not_authorized": "ليس لديك صلاحية استخدام هذا الأمر.",
    "command_cooldown": "الرجاء الانتظار {time} ثوانية قبل استخدام هذا الأمر مرة أخرى.",
}

# Admin panel responses
ADMIN_PANEL = {
    "title": "لوحة التحكم",
    "description": "إحصائيات ومعلومات عن نظام إشعارات المانهوا",
    "admin_only": "⛔ هذا الأمر متاح للمشرفين فقط.",
    "users_count_title": "📊 عدد المستخدمين المشتركين",
    "users_count_value": "**{count}** مستخدم نشط",
    "popular_manga_title": "🏆 أكثر المانهوا شعبية",
    "no_manga_data": "لا توجد بيانات كافية بعد",
    "manga_entry": "**{number}.** 📚 {manga}: **{count}** مشترك",
    "total_manga_title": "📈 إجمالي عدد المانهوا",
    "total_manga_value": "**{count}** مانهوا متاحة",
    "add_manga_success": "✅ تمت إضافة مانهوا '{manga}' بنجاح!",
    "add_manga_duplicate": "❌ المانهوا '{manga}' موجودة بالفعل في القائمة!",
    "add_manga_error": "❌ حدث خطأ أثناء إضافة المانهوا: {error}",
    "remove_manga_success": "✅ تم حذف مانهوا '{manga}' بنجاح!",
    "remove_manga_not_found": "❌ المانهوا '{manga}' غير موجودة في القائمة!",
    "remove_manga_error": "❌ حدث خطأ أثناء حذف المانهوا: {error}",
}

# Notification responses
NOTIFICATIONS = {
    "subscribed": "✅ تم اشتراكك بنجاح في إشعارات مانهوا: {manga}",
    "already_subscribed": "ℹ️ أنت مشترك بالفعل في إشعارات مانهوا: {manga}",
    "unsubscribed": "🚫 تم إلغاء اشتراكك من إشعارات مانهوا: {manga}",
    "not_subscribed": "ℹ️ أنت غير مشترك في إشعارات مانهوا: {manga}",
    "manga_not_found": "❓ لم يتم العثور على المانهوا: {manga}",
    "update_notification": "🎉 تم إصدار فصل جديد من مانهوا: {manga}\n\nهل أنت متحمس؟ اضغط على الرابط لقراءة الفصل الآن!",
    "new_manga_notification": "🌟 تمت إضافة مانهوا جديدة: {manga}\n\nاكتشف هذه المانهوا الجديدة واشترك للحصول على إشعارات التحديثات!",
    "episode_update_notification": "🎉 تم إصدار الفصل {episode} من مانهوا: {manga}\n\nهل أنت متحمس؟ اضغط على الرابط لقراءة الفصل الآن!",
    "unknown_episode_notification": "🎉 تم إصدار فصل جديد من مانهوا: {manga}\n\nلم نتمكن من تحديد رقم الفصل. هل أنت متحمس؟ اضغط على الرابط لقراءة الفصل الآن!",
    "position_change_notification": "🔄 مانهوا {manga} انتقلت إلى أعلى القائمة!\n\nقد يعني هذا أنها تلقت تحديثًا جديدًا. اضغط على الرابط للتحقق!"
}

# Recommendation responses
RECOMMENDATIONS = {
    "title": "توصيات المانهوا",
    "no_recommendations": "لم نتمكن من العثور على توصيات مناسبة في الوقت الحالي، يرجى المحاولة لاحقاً.",
    "recommendation_item": "**{number}.** [{title}]({url}) - {description}",
}

# User manga list responses
USER_MANGA = {
    "title": "📋 قائمة المانهوا الخاصة بك",
    "description": "المانهوا التي تتلقى إشعارات لفصولها الجديدة:",
    "no_subscriptions": "📭 أنت غير مشترك في أي إشعارات مانهوا حالياً.",
    "subscription_item": "**{number}.** 📚 {manga}",
}

# New content notifications
CONTENT_UPDATES = {
    "manga_update": "✨ فصل جديد من {title}",
    "manga_new": "🆕 مانهوا جديدة: {title}",
} 