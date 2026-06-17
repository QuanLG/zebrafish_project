from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from .models import UserRole, UserStatus, UserLoginLog

User = get_user_model()


class UserModelTests(TestCase):
    """用户模型单元测试"""

    def test_create_user(self):
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.status, UserStatus.PENDING)
        self.assertEqual(user.role, UserRole.OPERATOR)
        self.assertTrue(user.check_password('testpass123'))

    def test_create_superuser(self):
        admin = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_staff)
        self.assertEqual(admin.role, UserRole.ADMIN)

    def test_is_admin_property(self):
        admin = User.objects.create_superuser(
            username='admin2',
            email='admin2@example.com',
            password='adminpass123'
        )
        self.assertTrue(admin.is_admin)

        user = User.objects.create_user(
            username='normal',
            email='normal@example.com',
            password='normalpass123'
        )
        self.assertFalse(user.is_admin)


class UserAPITests(APITestCase):
    """用户管理 API 集成测试"""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            status=UserStatus.ACTIVE
        )
        self.active_user = User.objects.create_user(
            username='active',
            email='active@example.com',
            password='activepass123',
            status=UserStatus.ACTIVE
        )
        self.pending_user = User.objects.create_user(
            username='pending',
            email='pending@example.com',
            password='pendingpass123',
            status=UserStatus.PENDING
        )

    def test_register_success(self):
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'NewPass123!',
            'password_confirm': 'NewPass123!',
            'phone': '13800138000',
            'real_name': '张三'
        }
        response = self.client.post('/api/users/register/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['code'], 201)
        self.assertEqual(response.data['data']['username'], 'newuser')

    def test_register_password_mismatch(self):
        data = {
            'username': 'newuser2',
            'email': 'newuser2@example.com',
            'password': 'NewPass123!',
            'password_confirm': 'DifferentPass!',
        }
        response = self.client.post('/api/users/register/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_success(self):
        data = {
            'username': 'active',
            'password': 'activepass123'
        }
        response = self.client.post('/api/users/login/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['code'], 200)
        self.assertIn('tokens', response.data['data'])
        self.assertIn('access', response.data['data']['tokens'])

    def test_login_with_email(self):
        data = {
            'username': 'active@example.com',
            'password': 'activepass123'
        }
        response = self.client.post('/api/users/login/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['user']['email'], 'active@example.com')

    def test_login_pending_user(self):
        data = {
            'username': 'pending',
            'password': 'pendingpass123'
        }
        response = self.client.post('/api/users/login/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['code'], 403)

    def test_login_wrong_password(self):
        data = {
            'username': 'active',
            'password': 'wrongpassword'
        }
        response = self.client.post('/api/users/login/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_current_user(self):
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(self.active_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(refresh.access_token)}')

        response = self.client.get('/api/users/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['username'], 'active')

    def test_update_current_user(self):
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(self.active_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(refresh.access_token)}')

        data = {'real_name': '李四', 'phone': '13900139000'}
        response = self.client.patch('/api/users/me/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['real_name'], '李四')

    def test_change_password(self):
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(self.active_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(refresh.access_token)}')

        data = {
            'old_password': 'activepass123',
            'new_password': 'NewSecurePass456!',
            'new_password_confirm': 'NewSecurePass456!'
        }
        response = self.client.post('/api/users/me/password/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 验证旧密码失效
        login_data = {'username': 'active', 'password': 'activepass123'}
        response = self.client.post('/api/users/login/', login_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_list_users(self):
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(self.admin)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(refresh.access_token)}')

        response = self.client.get('/api/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data['data'])

    def test_non_admin_cannot_list_users(self):
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(self.active_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(refresh.access_token)}')

        response = self.client.get('/api/users/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_update_user_status(self):
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(self.admin)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(refresh.access_token)}')

        data = {'status': UserStatus.ACTIVE}
        response = self.client.patch(f'/api/users/{self.pending_user.id}/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_user.refresh_from_db()
        self.assertEqual(self.pending_user.status, UserStatus.ACTIVE)

    def test_admin_delete_user(self):
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(self.admin)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(refresh.access_token)}')

        response = self.client.delete(f'/api/users/{self.pending_user.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(User.objects.filter(id=self.pending_user.id).exists())

    def test_login_log_created(self):
        data = {
            'username': 'active',
            'password': 'activepass123'
        }
        self.client.post('/api/users/login/', data, format='json')
        self.assertTrue(UserLoginLog.objects.filter(user=self.active_user, status='success').exists())
