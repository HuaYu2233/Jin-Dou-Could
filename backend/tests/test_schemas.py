import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-verification-only-at-least-32-chars!!")

import pytest
from pydantic import ValidationError

from app.schemas.user import UserCreate, UserLogin, UserResponse, PasswordChange, _validate_password_complexity
from app.schemas.reset_password import ResetPasswordRequest, SecurityResetRequest


class TestPasswordValidation:
    def test_valid_password(self):
        assert _validate_password_complexity("Test1234") == "Test1234"

    def test_too_short(self):
        with pytest.raises(ValueError, match="8"):
            _validate_password_complexity("Ab1")

    def test_no_letter(self):
        with pytest.raises(ValueError, match="字母"):
            _validate_password_complexity("12345678")

    def test_no_digit(self):
        with pytest.raises(ValueError, match="数字"):
            _validate_password_complexity("abcdefgh")


class TestUserCreate:
    def test_valid(self):
        u = UserCreate(email="test@example.com", username="test", password="Test1234")
        assert u.email == "test@example.com"

    def test_invalid_email(self):
        with pytest.raises(ValidationError):
            UserCreate(email="not-email", username="test", password="Test1234")

    def test_weak_password(self):
        with pytest.raises(ValidationError):
            UserCreate(email="test@example.com", username="test", password="short")


class TestUserLogin:
    def test_valid(self):
        u = UserLogin(email="test@example.com", password="Test1234")
        assert u.email == "test@example.com"

    def test_invalid_email(self):
        with pytest.raises(ValidationError):
            UserLogin(email="bad", password="Test1234")


class TestPasswordChange:
    def test_valid(self):
        pc = PasswordChange(old_password="Old12345", new_password="NewPass1234")
        assert pc.new_password == "NewPass1234"

    def test_weak_new_password(self):
        with pytest.raises(ValidationError):
            PasswordChange(old_password="Old12345", new_password="short")


class TestResetPasswordRequest:
    def test_valid(self):
        r = ResetPasswordRequest(email="test@example.com", code="123456", new_password="NewPass1234")
        assert r.code == "123456"

    def test_weak_password(self):
        with pytest.raises(ValidationError):
            ResetPasswordRequest(email="test@example.com", code="123456", new_password="short")


class TestSecurityResetRequest:
    def test_valid(self):
        r = SecurityResetRequest(email="test@example.com", answer="小花", new_password="NewPass1234")
        assert r.answer == "小花"

    def test_weak_password(self):
        with pytest.raises(ValidationError):
            SecurityResetRequest(email="test@example.com", answer="小花", new_password="short")