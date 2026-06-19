[TOC]

# 参考资料

- github学习https://github.com/tiimgreen/github-cheat-sheet/blob/master/README.zh-cn.md


# 配置

## 全局配置

```sh
git config --global user.name "username"
git config --global user.email "useremail"

# 忽略换行符
git config --global core.autocrlf true

# 大小写敏感
git config core.ignorecase false  
```


## 局部配置

```sh
# 把--global去掉即可
git config user.name username 
```

## git ignore配置

http://git-scm.com/docs/gitignore

注意:如果文件以及在git仓库的索引缓存里，gitignore文件不生效

```
# 忽略文件格式
*.file_ext

# 忽略文件夹
/file_path/
# 关于 Pattern 规则，可以查看 git 的相关文档：http://git-scm.com/docs/gitignore 大致有以下几点：
# 空行不匹配任何内容，所以可以作为块分隔符；
1. `#` 开头表示注释，如果相匹配 `#`，可以在前面加一个反斜杠，即 `\\#`；
2. !file不匹配file
3. foo/ 匹配所有的foo文件夹内容
4. foo 匹配foo
5. **/foo 所有文件夹下的foo文件(夹)
6. foo/** foo文件夹下的所有文件
7. a/**/b 匹配a/b, a/x/b, a/y/b等
8. 匹配foo目录除了foo/bar/的内容
foo/
!foo/bar/
```

*注意* 已经加入大git-cache中的文件不会使用gitignore过滤，清除cache使用

```
git -rm -r --cached
```

# 仓库操作

## 常用操作

- git init 初始化本地仓库
- git status 显示git状态，有哪些文件将会被上传
- git reset 取消跟踪文件
- git log 显示提交历史
- git fetch --all 拉取cached内容
- git pull origin branchname 拉取远程分支
- git add remote code git@code.aliyun.com:578749341/tianchi-dubbo-agent.git 配置git地址才能免登


## clone最新代码

只获取最近的commit，不关心历史
```
git clone --depth=10 --branch=v1.0 https://github.com/xupingmao/xnote.git
```

## remote远程操作
- git remote add origin [url] 添加git地址，命名为origin
- git remote remove [name]移除git地址，name一般为origin
- git remote set-url [name] [new-url] 设置新的远程仓库地址
- git push -u [origin] [master]向origin地址的master分支提交 
- git remote -v 查看远程仓库url
- git remote rm origin 删除远程仓库origin
- git remote add origin your-url 增加url

```
# 查找删除的文件 

git log -p **/BranchCenterDoctorServiceInterface.java


# 跟踪所有分支
git remote set branches origin '*'
```

# commit操作

## 提交代码

- git push [origin] [local_branch]:[remote_branch] 把本地分支提交到远程分支 *这个比较好用...
- git commit --amend --author="Your Email" 修改上次提交邮箱

## revert vs reset

- revert回滚某个提交的修改内容
- reset是重新回到某个版本

## 回退某个文件的修改

- git checkout {sha1-of-a-commit} {/path/to/your/file} 恢复文件到之前的版本
- git checkout {sha1-of-a-commit}:{/path/to/your/file} {/new/name/of/the/file} 把文件之前版本另存为


## cherry-pick
Git cherry-pick可以选择某一个分支中的一个或几个commit(s)来进行操作。例如，假设我们有个稳定版本的分支，叫v2.0，另外还有个开发版本的分支v3.0，我们不能直接把两个分支合并，这样会导致稳定版本混乱，但是又想增加一个v3.0中的功能到v2.0中，这里就可以使用cherry-pick了。

```
git cherry-pick {commit_id}
1. 如果顺利，就会正常提交。结果：

Finished one cherry-pick.
# On branch old_cc
# Your branch is ahead of 'origin/old_cc' by 3 commits.

2. 如果在cherry-pick 的过程中出现了冲突

Automatic cherry-pick failed.  After resolving the conflicts,
mark the corrected paths with 'git add <paths>' or 'git rm <paths>'
and commit the result with: 

git commit -c 15a2b6c61927e5aed6718de89ad9dafba939a90b
        
```

## 放弃merge
- git merge --abort [Since git version 1.7.4]
- git reset --merge [prior git versions]


## commit常用前缀

在使用 Git 进行版本控制时，遵循提交信息规范可以提高代码的可读性和维护性。以下是常见的 Git 提交前缀及其含义：

- Add 新增文件、功能
- Remove 删除文件、功能
- Refactor 重构
- Improve 优化功能
- feat: 表示新增功能。例如，feat: 添加用户注册功能。
- fix: 表示修复 Bug。例如，fix: 修复登录页面崩溃的问题。
- docs: 表示文档相关的修改。例如，docs: 更新 README 文件。
- ui: 优化个人中心页面的按钮样式和布局
- style: 表示代码格式的调整，不影响逻辑。例如，style: 删除多余的空行。
- refactor: 表示代码重构，不涉及功能新增或 Bug 修复。例如，refactor: 重构用户验证逻辑。
- perf: 表示性能优化。例如，perf: 优化图片加载速度。
- test: 表示测试相关的修改。例如，test: 增加用户模块的单元测试。
- chore: 表示构建或辅助工具的变动。例如，chore: 更新依赖库。
- build: 表示构建系统或外部依赖的变更。例如，build: 升级 Webpack 到版本 5。
- ci: 表示持续集成配置的修改。例如，ci: 修改 GitHub Actions 配置文件。
- revert: 表示回滚之前的提交。例如，revert: 回滚 feat: 添加用户注册功能。

使用这些前缀可以让提交记录更清晰，便于团队协作和自动化工具解析，从而提高项目的维护效率和质量。



## rebase

作用：可以对某一段线性提交历史进行编辑和合并等操作。（就是合并commit）

```
git rebase -i HEAD~4 # 合并之前的4个commit
```

执行完这个命令之后，git会打开一个编辑器编辑命令，比如

```
pick b49ed2cb 调整样式
pick 15099f8f Fix 分享笔记的访问问题

# Rebase bd4ed2d5..15099f8f onto bd4ed2d5 (2 commands)
```

如果你不修改任何东西，commit记录是不会变化的，如果你想把commit合并到之前的commit，可以改成这样

```
squash b49ed2cb 调整样式   # 这个commit会被合并到下面15099f8f的commit 
pick 15099f8f Fix 分享笔记的访问问题

# Rebase bd4ed2d5..15099f8f onto bd4ed2d5 (2 commands)
```

PS：除了pick和squash，还有还几个命令，具体可以查看命令的帮助

## 修改commit信息

```
# 修改时间，执行下面命令后git会打开编辑器，其他内容也可以进行编辑
git commit --amend --date "Sat Apr 23 21:41:22 2022 +080"
```


# 分支操作

## 从远程仓库拉取分支

```
# 创建分支并且推送到远程
> git checkout -b <branch_name>
> git push -u origin <branch_name>

# 拉取分支
> git checkout <remote>/<branch>
> git checkout -b <new branch>
> git branch --set-upstream-to=<remote>/<branch> <local branch>

# 一步到位
git checkout -b local_name origin/remote_name
# 例子
git checkout -b local_name origin/feature/feature_111

## 注意必须先git pull，不然会报如下错误
## fatal: 'origin/feature/20180320_1987918_unlimit_agreementor_1' is not a commit and a branch 'unlimit' cannot be created from it

```

## 远程分支过多无法checkout

```
# 先创建一个分支
git checkout -b local_branch
# 然后执行pull命令
git pull origin remote_branch
```

## 删除分支
- git branch -d {branchname} 删除本地分支
- git push origin --delete {branch} 删除远程分支
- git branch 查看分支
- git branch -r[--remote] 显示远程分支

## 覆盖分支

```
# 本地覆盖远程
git push origin develop:master -f

# 远程覆盖本地
git fetch --all  
git reset --hard origin/master 
```

## 修改远程仓库同步分支
git branch --set-upstream-to=origin/<branch> [branch-name]

```sh
git branch --set-upstream-to=origin/feature_123
```

- git checkout <branch> 设置分支
- git checkout origin/<branch> checkout远程分支
- git checkout [filename] 下载文件

```sh
git checkout -- *Test.java # 下载匹配的文件
```

## 创建release/tag分支

```
# 注意tag名最好不要和分支名重复
git tag -a v1.4 -m 'my version 1.4'
git push origin {tagname} #必须显示指定tag
git push --tags # 推送所有的tag
git tag -d {tagname} # 删除tag
git push origin --delete {tagname} # 删除远程tag 和分支一样

# 展示操作
git tag -l # 展示tag列表
git tag -l -n2 # 展示tag详细描述（-n2表示展示2行描述）
```

## 分支管理的实践

- 开发分支名为 `feature_xxx` 或者 `dev0.1.1`
- 发布分支为 `v0.1.1` 或者 `release_v1.1.1`

# 内容查看和比较

## 内容对比

```sh
git diff <branch> # 当前分支与目标分支比较
git diff branch1 branch2
git diff commit_id1 commit_id2
```

## 查看文件修改历史

```
git log -p tagname.html

# 查看修改的作者和时间
git log -p sql.py | grep Date -B1

# 只查看提交内容（commit、作者、时间、描述）
git log --source sql.py | cat
```


# 危险操作

## 删除commit
- git reset --hard commit_id 

## 清除本地缓存
- git rm -r --cached .
- git add .

## 覆盖本地代码
- checkout dir/. 覆盖一级目录
- checkout dir/* 覆盖整个目录

## git pull强制覆盖

```
git fetch --all
git reset --hard origin/master
```

## 回滚merge代码

- git checkout master. then run a git log and get the id of the merge commit.
- git log. then revert to that commit:
- git revert -m 1 <merge-commit> With '-m 1' we tell git to revert to the first parent of the mergecommit on the master branch. ...
- git push 就OK了
- 如果要revert revert的提交，`git revert <commit-of-first-revert>`

## 硬删除commit

- git reset --hard `<commit id>` 回滚到目标commit
- git push -f 注意master分支一般无权限

## 彻底删除文件

有时候不小心把备份文件、敏感配置、编译结果等内容上传到了git仓库，这时候就需要把他们删除掉，可以使用如下操作

```
# 筛选出大文件（如果知道文件名，这一步可以跳过）
git rev-list --all | xargs -rL1 git ls-tree -r --long | sort -uk3 | sort -rnk4 | head -10

# 从commit日志里面删除文件记录
git filter-branch --tree-filter "rm -f {filepath}" -- --all

# 提交到远程分支
git push -f --all

# 重新下载git仓库就能发现文件被删除了

```

参考资料: https://blog.csdn.net/HappyRocking/article/details/89313501

```
git filter-branch --tree-filter "rm -f ctest" eab49d5938eea8f2dd6d56e38673f5b9844c78bf..HEAD
```

参考资料： https://cloud.tencent.com/developer/section/1138641

# 恢复

## 恢复HEAD

```sh
git reflog
git branch my-new-branch [SHA-1]
```


# 子模块

```
# 递归克隆子模块
git clone --recurse-submodules https://github.com/google/leveldb.git
```

# 其他功能

## 统计代码行

```
git log --format='%aN' | sort -u | while read name; do echo -en "$name\t"; git log --author="$name" --pretty=tformat: --numstat | awk '{ add += $1; subs += $2; loc += $1 - $2 } END { printf "added lines: %s, removed lines: %s, total lines: %s\n", add, subs, loc }' -; done
```

## 统计每天的提交次数

```
git log --date=short | grep Date | awk '{ print $2,$3,$4 }' | uniq -c
```

## 断点续传

https://blog.csdn.net/qq_35904259/article/details/61200880

git clone不能直接支持断点续传，使用git fetch处理

```
git mkdir example
git init
git fetch https://github/example/example.git
# 必须checkout HEAD
git checkout FETCH_HEAD
```