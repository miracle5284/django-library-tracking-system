from celery import shared_task
from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models.functions import Coalesce
from django.db.models import Value
from django.utils import timezone

from ..models import Loan
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


@shared_task(max_retries=3, bind=True)
def loan_reminder(self):
    try:
        today = timezone.now().date()
        loans = Loan.objects.select_related('member__user', 'book').filter(
            is_returned=False, return_date__lt=today
        ).values('member__user__first_name', 'member__user__email').annotate(
            books=Coalesce(ArrayAgg('book__title', distinct=True), Value([]))
        ).iterator(chunk_size=500)
        # print(1111, loans, list(loans))
        for loan in loans:
            print(loan)
            user_email = loan['member__user__email']
            user_name = loan['member__user__first_name']
            books = '\n'.join(loan['books'])

            print("Hi %s,\nYour following book loan are overdue:\n%s\nPlease return %s on ASAP" % (
                    user_name, books, len(books) == 1 and 'it' or 'them'))

            send_mail(
                message="Hi %s,\nYour following book loan are overdue:\n%s\nPlease return %s on ASAP" % (
                    user_name, books, len(books) == 1 and 'it' or 'them'),
                subject='Book Loan Overdue Reminder',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user_email],
                fail_silently=False,
            )
    except Exception as e:
        raise self.retry(exc=e, countdown=2 ** self.request.retries)
