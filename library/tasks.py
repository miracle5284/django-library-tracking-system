from celery import shared_task
from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import Loan
from django.core.mail import send_mail
from django.conf import settings

@shared_task
def send_loan_notification(loan_id):
    try:
        loan = Loan.objects.get(id=loan_id)
        member_email = loan.member.user.email
        book_title = loan.book.title
        send_mail(
            subject='Book Loaned Successfully',
            message=f'Hello {loan.member.user.username},\n\nYou have successfully loaned "{book_title}".\nPlease return it by the due date.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[member_email],
            fail_silently=False,
        )
    except Loan.DoesNotExist:
        pass


@shared_task(bind=True, max_retries=2)
def check_overdue_loans(self):
    try:
        today = timezone.now().date()
        loans = (Loan.objects.select_related('member__user__first_name', 'member__user__email', 'book_title')
                 .filter(is_returned=False, due_date__lt=today)
                 .values('member__user__first_name', 'member__user__email')
                 .annotate(books=Coalesce(ArrayAgg('book__title', distinct=True), []))
                 .iterator(chunk_size=100)
                 )
        for loan in loans:
            user_first_name = loan['member__user__first_name']
            user_email = loan['member__user__email']
            books = '\n'.join([f"- {title}" for title in loan['books']])

            message_template = "Dear %s, \n These borrowed books are overdue:\n%s\nPlease return them."

            if not user_email:
                continue
            send_mail(
                subject="Overdue Book Reminder",
                message=message_template % (user_first_name, books),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user_email],
                fail_silently=False,
            )
    except Exception as e:
        self.retry(exec=e, countdown= 2**self.request.retries)