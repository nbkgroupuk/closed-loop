<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>BlackRock Admin</title>
  <style>
    body{font-family: Arial, Helvetica, sans-serif; margin:20px;}
    .panel{padding:10px;border:1px solid #ddd;margin-bottom:10px;}
    table{width:100%;border-collapse:collapse;}
    th,td{padding:6px;border:1px solid #eee;text-align:left;}
    .btn{padding:6px 10px;background:#0b76ef;color:#fff;border-radius:4px;text-decoration:none;}
  </style>
  <script src="/static/admin.js"></script>
</head>
<body>
  <h1>BlackRock Admin Dashboard</h1>
  <div>
    <a href="/admin/dashboard">Dashboard</a>
  </div>
  <hr/>
  {% block body %}{% endblock %}
</body>
</html>
