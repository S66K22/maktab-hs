# پروندهٔ انتقال گفتگو --- پروژهٔ دستیار سالن LUNA

این فایل را در حساب دیگر بارگذاری کنید و بگویید: «این فایل خلاصهٔ سابقهٔ
پروژه است؛ از بخش وضعیت فعلی ادامه بده.»

## ۱. روش همکاری موردنظر کاربر

-   زبان ترجیحی: فارسی؛ اصطلاحات فنی و نام‌های Python می‌توانند انگلیسی
    بمانند.
-   کاربر پروژه را آموزشی و مرحله‌به‌مرحله پیش می‌برد و از دستیار می‌خواهد
    نقش معلم/راهنما داشته باشد: مسیر و سرنخ بدهد، سؤال‌های کوتاه بپرسد و
    کاربر را در تصمیم‌گیری مشارکت دهد.
-   از بازنویسی کامل پروژه بدون درخواست کاربر پرهیز کن. هر بار یک مفهوم
    یا گام را توضیح بده.
-   کاربر استفاده از dictionary برای نگاشت نام ابزار به handler را به
    if/elifهای متعدد ترجیح می‌دهد و تا جای ممکن خطای کنترل‌شده را به توقف
    برنامه ترجیح می‌دهد.

## ۲. هدف پروژه

ساخت `SalonAssistant` برای دستیار رزرو سالن LUNA / Studio Linden. مدل
زبانی می‌تواند درخواست اجرای ابزار بدهد، اما کنترل‌کنندهٔ Python باید
اعتبارسنجی، سیاست‌های رزرو، هویت مشتری، تأیید مشتری، حریم خصوصی و ایمنی
اجرای ابزارها را enforce کند.

اصول: - backend مرجع حقیقت برای داده‌ها و اعمال رزرو است. - مدل نباید
مرجع حقیقت برای وضعیت رزرو، قیمت، مجوز یا هویت باشد. - کنترل‌کننده باید
آرگومان ابزار را اعتبارسنجی کند و فقط نتیجهٔ قابل اتکا را به مدل بدهد. -
مدل پاسخ نهایی قابل‌فهم برای مشتری را تولید می‌کند. - شناسه‌ها و داده‌های
حساس نباید بی‌دلیل افشا شوند.

## ۳. قواعد و تصمیم‌های قبلی

### رزرو و تأیید

-   اگر زمان پیشنهادی هنوز تأیید نهایی مشتری را ندارد، اقدام باید در
    وضعیت `pending` بماند.
-   در نتیجهٔ غیرنهایی/مشروط، پاسخ قبلی و درخواست قبلی باید طبق منطق
    پروژه پاک یا بازنشانی شوند تا دادهٔ قدیمی اشتباهاً دوباره استفاده
    نشود.
-   اگر مشتری تأیید کرد و درخواست باید دوباره ارسال شود، همان
    `request_key` قبلی استفاده شود تا idempotency حفظ شود.
-   مثال‌های قیمت/هزینه‌ای که قبلاً بررسی شده‌اند:
    -   زمان باقی‌ماندهٔ `24h + 1s`: صفر سنت.
    -   دقیقاً `24h`: صفر سنت.
    -   `23h 59m`: `1750` سنت.
    -   دقیقاً `2h`: `1750` سنت.
    -   `1h 59m`: `3500` سنت.
    -   دقیقاً زمان شروع: `ValueError`.
-   این‌ها نمونه‌های قواعد موردبحث‌اند؛ پیش از استفاده در منطق نهایی باید
    با سیاست قطعی پروژه تطبیق داده شوند.

### هویت و حریم خصوصی

-   مشتری نباید به اطلاعات حساس دسترسی پیدا کند یا آن‌ها را یاد بگیرد.
-   برای `get_my_bookings` بهتر است مدل نتواند `session_id` دلخواه را
    انتخاب کند؛ کنترل‌کننده باید نشست معتبر را از زمینهٔ درخواست تأمین
    کند.
-   یک مشتری می‌تواند چند نشست مختلف داشته باشد؛ نشست مکالمه با هویت
    مشتری یکی نیست.
-   محدودیت‌هایی مثل حداکثر تعداد رزروهای فعال باید در backend و به‌صورت
    اتمیک enforce شوند، نه فقط در مکالمه یا مدل.

## ۴. آخرین پیش‌نویس کد کاربر

کد زیر آخرین نسخهٔ ارسال‌شده را به‌صورت تقریبی حفظ می‌کند و عمداً اصلاح نشده
است تا وضعیت فعلی روشن بماند:

``` python
class SalonAssistant:
    def __init__(self, model, backend, clock):
        self.model, self.backend, self.clock = model, backend, clock
        self.sessions, self.audit = {}, []
        self.handlers = {
            "list_services": self._list_services,
            "find_slots": self._find_slots,
            "get_my_bookings": self._get_my_bookings
        }
        self.expected_arguments = {
            "list_services": '',
            "find_slots": {'service_id', 'date', 'stylist_id'},
            "get_my_bookings': {"session_id"}
        }
        self.expected_argument_types = {
            "find_slots": {"service_id": str, "date": datetime.date, "stylist_id": str},
            "get_my_bookings": {"session_id": str}
        }

    def _list_services(self):
        pass

    def _find_slots(self, service_id, date, stylist_id=None):
        pass

    def _get_my_bookings(self, session_id):
        if session_id not in self.sessions:
            raise KeyError("Session does not exist")
        # Get info from backend

    def _dispatch_tool(self, name, arguments):
        if name is None or name == "" or arguments is None or arguments not isinstance(arguments, dict):
            return {
                "status": "error",
                "error_type": "parse_tool",
                "data": None
            }
        handler = self.handlers.get(name)
        if handler is None:
            return {
                "status": "error",
                "error_type": "unknown_tool",
                "data": None
            }
        return handler

    def _parse_arguments(self, arguments):
        if isinstance(arguments, dict):
            return arguments
        try:
            arguments = json.loads(arguments);
        except json.JSONDecodeError as exc::
            raise ValueError('malformed JSON arguments') from exc
        return arguments

    def _validate_tool_arguments(self, name, arguments):
        required_fields = self.expected_arguments.get('name')
        if required_fields is None:
            return

        missing = required_fields - set(arguments)
        extras = set(arguments) - required_fields

        if missing or extras:
            return "error"

    def open_session(self, session_id, customer_id):
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "customer_id": customer_id,
                "messages": [],
                "pending_action": None
            }
        else:
            raise ValueError("Session belongs to another customer")

    def handle(self, session_id, user_text):
        raise NotImplementedError('handle')
```

توجه: در پیش‌نویس احتمالاً غلط تایپی در کلید `"get_my_bookings'` وجود
دارد.

## ۵. ابزارها و schemaها

کاربر `TOOL_SCHEMAS` را با قالب OpenAI-style می‌سازد. در گفتگو این
ابزارها نمایش داده شده‌اند:

### `list_services`

-   توضیح: `List available salon services.`
-   پارامترها: object با `properties: {}`، `required: []` و
    `additionalProperties: False`.

### `find_slots`

-   `service_id`: رشته، شناسهٔ یکتا.
-   `date`: رشته با قالب `YYYY-MM-DD`.
-   `stylist_id`: رشتهٔ اختیاری، شناسهٔ یکتا.
-   فیلدهای اجباری: `service_id` و `date`.
-   `additionalProperties: False`.

در `handlers` همچنین `get_my_bookings` وجود دارد؛ اگر مدل قرار است آن را
صدا بزند، schema متناظر هم لازم است. بااین‌حال `session_id` نباید پارامتر
انتخابی مدل باشد؛ کنترل‌کننده باید آن را از نشست معتبر تأمین کند.

## ۶. مفاهیم فنی که قبلاً بررسی شده‌اند

### Dispatch و handler

-   `self.handlers.get(name)` اگر ابزار ثبت نشده باشد `None` برمی‌گرداند؛
    `self.handlers[name]` ممکن است `KeyError` ایجاد کند.
-   `handler = self.handlers.get(name)` فقط تابع را می‌گیرد؛ `handler()`
    آن را اجرا می‌کند.
-   در `_dispatch_tool` پیش‌نویس فعلی `return handler` فقط تابع را
    برمی‌گرداند و آن را اجرا نمی‌کند.
-   بررسی نوع باید به این صورت باشد: `not isinstance(arguments, dict)`؛
    عبارت `arguments not isinstance(...)` از نظر نحوی نادرست است.

### Parse در برابر validation

-   `_parse_arguments` رشتهٔ JSON را به مقدار Python تبدیل می‌کند.
-   JSON معتبر لزوماً dict/object نیست؛ ممکن است list، عدد یا `null`
    باشد. اگر ابزار object انتظار دارد، این خطای validation است، نه
    parse.
-   برای JSON نامعتبر می‌توان `json.JSONDecodeError` را گرفت.
-   `except json.JSONDecodeError as exc::` دو نقطه دارد و خطای نحوی است.
-   استفاده از `json.loads(arguments)` درست است؛ مراقب غلط تایپی
    `arguements` باشید.
-   خروجی parse و خروجی خطا نباید با هم اشتباه گرفته شوند؛ از یک قرارداد
    یکنواخت برای نتیجه‌ها استفاده کن.

### Required fields و allowed fields

-   `required` فقط فیلدهای اجباری را مشخص می‌کند.
-   `properties` تمام فیلدهای مجاز را مشخص می‌کند؛ بعضی از آن‌ها می‌توانند
    اختیاری باشند.
-   برای `find_slots`، `stylist_id` مجاز است اما اجباری نیست.
-   منطق مفهومی:
    -   `missing = required_fields - set(arguments)`
    -   `extras = set(arguments) - allowed_fields`
-   در کد فعلی `self.expected_arguments.get('name')` باید دست‌کم
    `.get(name)` باشد؛ پیشنهاد بهتر این است که schema منبع حقیقت باشد و
    اطلاعات در چند dict جداگانه تکرار نشود.

### تاریخ

-   ورودی JSON برای `date` یک رشته با قالب `YYYY-MM-DD` است؛ ابتدا رشته
    و قالب آن را اعتبارسنجی کن.
-   پس از آن، در صورت نیاز آن را به `datetime.date` تبدیل کن.
-   قرار دادن `datetime.date` در `expected_argument_types` با ورودی خام
    JSON سازگار نیست.

### نشست

-   ساختار نشست:

    ``` python
    {
        "customer_id": customer_id,
        "messages": [],
        "pending_action": None
    }
    ```

-   هر نشست باید لیست `messages` مستقل داشته باشد.

-   منطق فعلی `open_session` اگر `session_id` موجود باشد همیشه خطا
    می‌دهد، حتی اگر متعلق به همان مشتری باشد؛ پیام
    `Session belongs to another customer` ممکن است در آن حالت دقیق نباشد
    و سیاست آن باید مشخص شود.

## ۷. نقطهٔ دقیق ادامهٔ گفتگو

آخرین سؤال راهنما از کاربر این بود:

> اگر `name` در `self.schemas` وجود نداشته باشد، Validator باید «invalid
> input» برگرداند یا «unknown tool»؟ چرا این خطاها را جدا نگه می‌داریم؟

پاسخ آموزشی: - نام ابزار ثبت نشده است: `unknown_tool`؛ خود ابزار
ناشناخته است. - ابزار شناخته شده ولی آرگومان‌ها ناقص، اضافی یا نامعتبرند:
`validation_error`. - این دو خطا جدا هستند چون علت و محل رفع آن‌ها متفاوت
است: اولی به نام/ثبت ابزار مربوط است و دومی به انطباق آرگومان‌ها با
schema همان ابزار.

پس از توضیح این پاسخ، از کاربر بخواه تصمیم بگیرد که آیا `self.schemas`
را از `TOOL_SCHEMAS` بسازد یا خودش ساختار را پیاده‌سازی کند. همچنان
مرحله‌ای پیش برو.

## ۸. گام‌های بعدی پیشنهادی

1.  مفهوم `unknown_tool` در برابر `validation_error` را تثبیت کن.
2.  از `TOOL_SCHEMAS` یک `self.schemas` بساز که کلید آن نام ابزار و
    مقدار آن schema مربوط باشد.
3.  validator را بر پایهٔ `parameters.properties`، `parameters.required`
    و `additionalProperties` طراحی کن.
4.  parse، validation و dispatch را جدا نگه دار.
5.  دربارهٔ قرارداد خطا تصمیم بگیر؛ کاربر ترجیح می‌دهد تا حد ممکن خطای
    کنترل‌شده برگردد و برنامه بی‌دلیل متوقف نشود.
6.  `_dispatch_tool` را کامل کن تا ابزار ناشناخته، آرگومان نامعتبر و
    خطای اجرای handler از هم قابل تشخیص باشند.
7.  هویت `get_my_bookings` را از کنترل‌کننده تأمین کن، نه از آرگومان مدل.
8.  سپس handlerها را به backend متصل کن و `handle` را پیاده‌سازی کن.


"description": "Appointment start datetime in ISO 8601 format"
book_schema = next(
    t["function"]["parameters"]
    for t in TOOL_SCHEMAS
    if t["function"]["name"] == "book_appointment"
)

assert set(book_schema["required"]) == {
    "service_id", "stylist_id", "start"
}
assert set(book_schema["required"]) == set(book_schema["properties"])
assert book_schema["additionalProperties"] is False

print("book_appointment schema passed")